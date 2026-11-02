// Escenario del circuito de Mónaco: cielo HDR, mar con puerto y yates, ciudad de
// fachadas mediterráneas, colinas con bosque, palmeras, público en graderías,
// faroles y túnel. Todo esto es decoración: no cambia la física. Se ubica FUERA
// del muro del simulador, así lo que se ve nunca contradice lo que calcula Python.
//
// Texturas y cielos: Poly Haven (CC0). Faroles: modelo street_lamp_01 de Poly Haven.

import * as THREE from "three";
import { Sky } from "three/addons/objects/Sky.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { pbr, cielo, registrar } from "./texturas.js";

const rnd = (() => { let s = 12345; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();
const ARRIBA = new THREE.Vector3(0, 1, 0);

// ------------------------------------------------------------------ utilidades

// Distancia aproximada de un punto a la línea central (cubetas de 20 m)
function crearDistancia(centro) {
  const C = 20, cubetas = new Map();
  for (const [s, x, y] of centro) {
    const k = `${Math.floor(x / C)},${Math.floor(y / C)}`;
    if (!cubetas.has(k)) cubetas.set(k, []);
    cubetas.get(k).push([x, y, s]);
  }
  return (x, y) => {
    const cx = Math.floor(x / C), cy = Math.floor(y / C);
    let mejor = 1e9, sMejor = 0;
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const [px, py, s] of cubetas.get(`${cx + i},${cy + j}`) || []) {
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d < mejor) { mejor = d; sMejor = s; }
      }
    }
    return [Math.sqrt(mejor), sMejor];
  };
}

// Ruido de valor 2D y fbm (para colinas y follaje)
function hash(x, y) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}
function ruido(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi), b = hash(xi + 1, yi), c = hash(xi, yi + 1), d = hash(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, y, oct = 5) {
  let s = 0, a = 0.5, f = 1;
  for (let i = 0; i < oct; i++) { s += a * ruido(x * f, y * f); f *= 2.03; a *= 0.5; }
  return s;
}

// Constructor de geometría por caras (posiciones, uv y color por vértice)
class Malla {
  constructor() { this.pos = []; this.uv = []; this.col = []; }
  // Cuadrilátero a-b-c-d (en orden) con la cara mirando hacia `fuera`
  quad(a, b, c, d, uvs, color, fuera) {
    const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(d, a));
    let vs = [a, b, c, d], us = uvs;
    if (fuera && n.dot(fuera) < 0) { vs = [a, d, c, b]; us = [uvs[0], uvs[3], uvs[2], uvs[1]]; }
    for (const i of [0, 1, 2, 0, 2, 3]) {
      this.pos.push(vs[i].x, vs[i].y, vs[i].z);
      this.uv.push(us[i][0], us[i][1]);
      this.col.push(color.r, color.g, color.b);
    }
  }
  tri(a, b, c, uvs, color, fuera) {
    const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));
    let vs = [a, b, c], us = uvs;
    if (fuera && n.dot(fuera) < 0) { vs = [a, c, b]; us = [uvs[0], uvs[2], uvs[1]]; }
    for (let i = 0; i < 3; i++) {
      this.pos.push(vs[i].x, vs[i].y, vs[i].z);
      this.uv.push(us[i][0], us[i][1]);
      this.col.push(color.r, color.g, color.b);
    }
  }
  geometria() {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(this.uv, 2));
    g.setAttribute("color", new THREE.Float32BufferAttribute(this.col, 3));
    g.computeVertexNormals();
    return g;
  }
}

// ------------------------------------------------------------------ texturas dibujadas

function lienzo(w, h) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  return [c, c.getContext("2d")];
}
function aTextura(c, { repetir = true, srgb = true } = {}) {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repetir) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  return t;
}

// Fachada mediterránea: un módulo = un vano (3.2 m) × un piso (3.2 m).
// El fondo es estuco blanco: el color de cada edificio se pone por vértice.
const VANO = 3.2;
function texturaFachada(persiana) {
  const [c, g] = lienzo(256, 256);
  g.fillStyle = "#f4f0e8"; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 2500; i++) {                     // textura del estuco
    const v = 225 + Math.random() * 30;
    g.fillStyle = `rgba(${v},${v - 4},${v - 12},0.35)`;
    g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2);
  }
  g.fillStyle = "rgba(0,0,0,0.10)"; g.fillRect(0, 0, 256, 10);       // cornisa del piso
  g.fillStyle = "rgba(255,255,255,0.6)"; g.fillRect(0, 10, 256, 3);
  const x0 = 84, x1 = 172, y0 = 56, y1 = 214;
  // Persianas abiertas a los lados
  g.fillStyle = persiana;
  g.fillRect(x0 - 34, y0, 30, y1 - y0); g.fillRect(x1 + 4, y0, 30, y1 - y0);
  g.strokeStyle = "rgba(0,0,0,0.25)"; g.lineWidth = 2;
  for (let y = y0 + 6; y < y1; y += 7) {
    g.beginPath(); g.moveTo(x0 - 32, y); g.lineTo(x0 - 6, y); g.stroke();
    g.beginPath(); g.moveTo(x1 + 6, y); g.lineTo(x1 + 32, y); g.stroke();
  }
  // Marco y vidrio con reflejo del cielo
  g.fillStyle = "#fbfaf7"; g.fillRect(x0 - 6, y0 - 8, x1 - x0 + 12, y1 - y0 + 14);
  const vid = g.createLinearGradient(0, y0, 0, y1);
  vid.addColorStop(0, "#9fb4c8"); vid.addColorStop(0.45, "#3d4f63"); vid.addColorStop(1, "#1d2733");
  g.fillStyle = vid; g.fillRect(x0, y0, x1 - x0, y1 - y0);
  g.fillStyle = "rgba(255,255,255,0.18)";
  g.beginPath(); g.moveTo(x0 + 10, y1); g.lineTo(x0 + 40, y0); g.lineTo(x0 + 58, y0); g.lineTo(x0 + 28, y1); g.fill();
  g.fillStyle = "#fbfaf7"; g.fillRect((x0 + x1) / 2 - 3, y0, 6, y1 - y0); g.fillRect(x0, y0 + 60, x1 - x0, 5);
  // Balcón con baranda de hierro
  g.fillStyle = "#e9e4da"; g.fillRect(x0 - 16, y1 - 4, x1 - x0 + 32, 10);
  g.strokeStyle = "#2b2b2b"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(x0 - 14, y1 - 34); g.lineTo(x1 + 14, y1 - 34); g.stroke();
  for (let x = x0 - 12; x <= x1 + 14; x += 8) { g.beginPath(); g.moveTo(x, y1 - 34); g.lineTo(x, y1 - 4); g.stroke(); }
  return aTextura(c);
}

function texturaBandera(colores) {
  const [c, g] = lienzo(96, 64);
  colores.forEach((col, i) => { g.fillStyle = col; g.fillRect(0, (i * 64) / colores.length, 96, 64 / colores.length + 1); });
  return aTextura(c, { repetir: false });
}

// Torre moderna: un módulo = vano × piso con losa de balcón blanca, baranda de vidrio
// verdoso y ventanal oscuro de piso a techo. La rugosidad hace que el vidrio refleje el cielo.
function texturaTorre() {
  const [c, g] = lienzo(256, 256), [cr, gr] = lienzo(256, 256);
  g.fillStyle = "#f3f1ec"; g.fillRect(0, 0, 256, 256);
  gr.fillStyle = "#e0e0e0"; gr.fillRect(0, 0, 256, 256);           // concreto: áspero
  const vid = g.createLinearGradient(0, 40, 0, 220);
  vid.addColorStop(0, "#5e7487"); vid.addColorStop(0.5, "#2c3a48"); vid.addColorStop(1, "#1b242e");
  g.fillStyle = vid; g.fillRect(14, 30, 228, 186);                 // ventanal
  gr.fillStyle = "#262626"; gr.fillRect(14, 30, 228, 186);         // vidrio: liso
  g.fillStyle = "#cfd3d6"; for (const x of [14, 88, 166, 238]) g.fillRect(x, 30, 4, 186);   // marcos
  g.fillStyle = "rgba(255,255,255,0.10)"; g.beginPath(); g.moveTo(30, 216); g.lineTo(90, 30); g.lineTo(120, 30); g.lineTo(60, 216); g.fill();
  g.fillStyle = "rgba(150,190,180,0.55)"; g.fillRect(0, 160, 256, 56);   // baranda de vidrio
  gr.fillStyle = "#333333"; gr.fillRect(0, 160, 256, 56);
  g.fillStyle = "#9aa3a8"; g.fillRect(0, 158, 256, 3);                   // pasamanos
  g.fillStyle = "#fbfaf7"; g.fillRect(0, 216, 256, 40);                  // losa del balcón
  g.fillStyle = "rgba(0,0,0,0.18)"; g.fillRect(0, 216, 256, 5);
  return { map: aTextura(c), rugosidad: aTextura(cr, { srgb: false }) };
}

// Locales del primer piso: 4 vitrinas distintas con toldo de rayas y letrero
function texturaTiendas() {
  const [c, g] = lienzo(1024, 256), [cr, gr] = lienzo(1024, 256);
  gr.fillStyle = "#dddddd"; gr.fillRect(0, 0, 1024, 256);
  const tiendas = [["CAFÉ", "#7a1f2b", "#f3efe6"], ["BOUTIQUE", "#1f2937", "#d6b46a"], ["GELATO", "#0f766e", "#ffffff"], ["PHARMACIE", "#166534", "#ffffff"]];
  tiendas.forEach(([nombre, col, letra], i) => {
    const x = i * 256;
    g.fillStyle = "#e9e1d3"; g.fillRect(x, 0, 256, 256);                 // piedra
    g.fillStyle = col; g.fillRect(x + 10, 40, 236, 30);                   // letrero
    g.fillStyle = letra; g.font = "700 22px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(nombre, x + 128, 56);
    for (let k = 0; k < 12; k++) {                                       // toldo de rayas
      g.fillStyle = k % 2 ? col : "#f4f1ea";
      g.beginPath(); g.moveTo(x + 8 + k * 20, 72); g.lineTo(x + 28 + k * 20, 72); g.lineTo(x + 30 + k * 20, 100); g.lineTo(x + 6 + k * 20, 100); g.fill();
    }
    const vid = g.createLinearGradient(0, 104, 0, 244);
    vid.addColorStop(0, "#3a4652"); vid.addColorStop(1, "#141a20");
    g.fillStyle = vid; g.fillRect(x + 16, 104, 224, 140);                 // vitrina
    gr.fillStyle = "#202020"; gr.fillRect(x + 16, 104, 224, 140);
    g.fillStyle = "rgba(255,226,170,0.25)"; g.fillRect(x + 30, 150, 196, 60);   // luz interior
    g.fillStyle = "#2a2a2a"; g.fillRect(x + 126, 104, 4, 140);
    g.fillStyle = "rgba(255,255,255,0.12)"; g.beginPath(); g.moveTo(x + 40, 244); g.lineTo(x + 90, 104); g.lineTo(x + 110, 104); g.lineTo(x + 60, 244); g.fill();
  });
  return { map: aTextura(c), rugosidad: aTextura(cr, { srgb: false }) };
}

// Marquesina de la gradería principal: un tablero de 24 m que se repite
function texturaMarquesina() {
  const [c, g] = lienzo(2048, 96);
  const fondo = g.createLinearGradient(0, 0, 0, 96);
  fondo.addColorStop(0, "#0b1d5c"); fondo.addColorStop(1, "#06103a");
  g.fillStyle = fondo; g.fillRect(0, 0, 2048, 96);
  g.fillStyle = "#ffd23f"; g.fillRect(0, 0, 2048, 6); g.fillRect(0, 90, 2048, 6);
  g.font = "italic 900 54px Inter, Arial"; g.textBaseline = "middle"; g.textAlign = "center";
  g.fillStyle = "#ffffff"; g.fillText("AUTONOMOUS RALLY", 560, 50);
  g.fillStyle = "#ffd23f"; g.fillText("MONACO 2026", 1500, 50);
  g.fillStyle = "rgba(255,255,255,0.35)"; g.fillRect(1020, 24, 4, 52);
  return aTextura(c);
}

function texturaHoja() {   // hoja de palmera con transparencia
  const [c, g] = lienzo(64, 256);
  g.strokeStyle = "#5b4a2a"; g.lineWidth = 3;
  g.beginPath(); g.moveTo(32, 0); g.lineTo(32, 256); g.stroke();
  for (let y = 6; y < 250; y += 5) {
    const ancho = 30 * Math.sin((y / 256) * Math.PI) + 2;
    const verde = 60 + Math.random() * 40;
    g.strokeStyle = `rgb(${40 + Math.random() * 20},${verde + 50},${30 + Math.random() * 15})`;
    g.lineWidth = 2.2;
    g.beginPath(); g.moveTo(32, y); g.lineTo(32 - ancho, y + 9); g.stroke();
    g.beginPath(); g.moveTo(32, y); g.lineTo(32 + ancho, y + 9); g.stroke();
  }
  return aTextura(c, { repetir: false });
}

function texturaCorteza() {
  const [c, g] = lienzo(64, 256);
  g.fillStyle = "#7a6248"; g.fillRect(0, 0, 64, 256);
  for (let y = 0; y < 256; y += 9) {
    g.fillStyle = `rgba(40,28,15,${0.35 + Math.random() * 0.2})`; g.fillRect(0, y, 64, 3);
    g.fillStyle = "rgba(200,170,130,0.25)"; g.fillRect(0, y + 3, 64, 2);
  }
  return aTextura(c);
}

// Tarjeta de agujas de pino: manojos de agujas que salen de ramitas, fondo transparente.
// El centro (0.5, 0.5) es opaco y oscuro: lo usa el núcleo de la copa.
function texturaAgujas() {
  const [c, g] = lienzo(512, 512);
  g.clearRect(0, 0, 512, 512);
  const r0 = g.createRadialGradient(256, 256, 0, 256, 256, 60);
  r0.addColorStop(0, "#1f2d17"); r0.addColorStop(0.8, "#1f2d17"); r0.addColorStop(1, "rgba(31,45,23,0)");
  g.fillStyle = r0; g.beginPath(); g.arc(256, 256, 60, 0, 7); g.fill();
  g.lineCap = "round";
  for (let i = 0; i < 70; i++) {                         // manojos
    const a = Math.random() * Math.PI * 2, r = 40 + Math.sqrt(Math.random()) * 175;
    const cx = 256 + Math.cos(a) * r, cy = 256 + Math.sin(a) * r;
    g.strokeStyle = "#4a3a28"; g.lineWidth = 2.2;          // ramita
    g.beginPath(); g.moveTo(256 + Math.cos(a) * (r - 30), 256 + Math.sin(a) * (r - 30)); g.lineTo(cx, cy); g.stroke();
    const luz = 0.6 + 0.4 * (r / 215);
    for (let k = 0; k < 34; k++) {                       // agujas
      const b = a + (Math.random() - 0.5) * 2.6, l = 14 + Math.random() * 20;
      const h = 88 + Math.random() * 30, s = 30 + Math.random() * 25, L = (16 + Math.random() * 22) * luz;
      g.strokeStyle = `hsl(${h},${s}%,${L}%)`; g.lineWidth = 1.4 + Math.random();
      g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(b) * l, cy + Math.sin(b) * l); g.stroke();
    }
  }
  return aTextura(c, { repetir: false });
}

// ------------------------------------------------------------------ escenario

export function construirEscenario({ scene, renderer, pista, P }) {
  // Diagnóstico de rendimiento: ?sin=publico,arboles,... oculta esas partes
  const sin = new Set((new URLSearchParams(location.search).get("sin") || "").split(","));
  function agregar(grupo, ...objetos) {
    for (const o of objetos) { o.userData.grupo = grupo; o.visible = !sin.has(grupo); scene.add(o); }
  }
  const [MX, MY] = pista.mapa;
  const dist = crearDistancia(pista.centro);
  // ¿El punto está dentro del circuito? (prueba del rayo sobre el polígono de la línea central)
  const poli = pista.centro.filter((_, i) => i % 4 === 0).map(([, x, y]) => [x, y]);
  const dentro = (x, y) => {
    let c = false;
    for (let i = 0, j = poli.length - 1; i < poli.length; j = i++) {
      const [xi, yi] = poli[i], [xj, yj] = poli[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  const muro = pista.ancho / 2 + pista.escape;
  const ys = pista.centro.map((c) => c[2]);
  const ORILLA = Math.min(...ys) - muro - 6; // el mar empieza al sur de la recta de meta
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Vector3(), color = new THREE.Color();

  // ---------------------------------------------------------------- cielo
  // Mientras llega el HDR se usa el cielo procedural; después, la foto real.
  const sky = new Sky();
  sky.scale.setScalar(2500);
  agregar("cielo", sky);
  const u = sky.material.uniforms;
  u.turbidity.value = 6; u.rayleigh.value = 1.6; u.mieCoefficient.value = 0.006; u.mieDirectionalG.value = 0.86;
  const sol = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(84), THREE.MathUtils.degToRad(15));
  u.sunPosition.value.copy(sol);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const cielos = {};
  let mojadoActual = false;
  Promise.all([cielo("belfast_sunset_puresky"), cielo("kloofendal_overcast_puresky")]).then(([seco, nublado]) => {
    cielos.seco = { ...seco, env: pmrem.fromEquirectangular(seco.tex).texture };
    cielos.mojado = { ...nublado, env: pmrem.fromEquirectangular(nublado.tex).texture };
    sky.visible = false;
    aplicarClima(mojadoActual);
  }).catch((err) => console.warn("Cielo HDR no disponible; se usa el procedural.", err));
  const envProc = pmrem.fromScene((() => { const s = new THREE.Scene(); s.add(sky.clone()); return s; })()).texture;

  // ---------------------------------------------------------------- mar y puerto
  // Mar: superficie brillante con olas (mapa de relieve que se desplaza) que refleja el cielo
  // HDR. Antes se usaba Water, que dibuja la escena entera otra vez en cada cuadro (muy lento).
  const olas = new THREE.TextureLoader().load(
    // El paquete npm de three no incluye examples/textures: se toma del repo en GitHub
    "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r170/examples/textures/waternormals.jpg",
    (t) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(220, 220); });
  const agua = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.MeshPhysicalMaterial({
    color: 0x0a3550, roughness: 0.08, metalness: 0.0, normalMap: olas, normalScale: new THREE.Vector2(0.35, 0.35),
    clearcoat: 1, clearcoatRoughness: 0.05,
  }));
  agua.rotation.x = -Math.PI / 2;
  agua.position.set(0, -0.6, -ORILLA + 2000);  // z = -y: el mar ocupa todo y < ORILLA
  agregar("mar", agua);

  // Malecón y muelles de piedra (Port Hercule)
  const matPiedra = new THREE.MeshStandardMaterial({ color: 0xd8cdb8, roughness: 0.9 });
  pbr(matPiedra, "cobblestone_01", { repetir: [300, 2] });
  const malecon = new THREE.Mesh(new THREE.BoxGeometry(3000, 1.4, 6), matPiedra);
  malecon.position.copy(P(0, ORILLA - 3, 0.1));
  malecon.receiveShadow = true;
  agregar("mar", malecon);
  const muelles = [];
  for (const x of [-140, -60, 30, 110]) {
    const largo = 90 + rnd() * 40;
    const muelle = new THREE.Mesh(new THREE.BoxGeometry(5, 1.2, largo), matPiedra.clone());
    pbr(muelle.material, "cobblestone_01", { repetir: [2, largo / 4] });
    muelle.position.copy(P(x, ORILLA - 6 - largo / 2, 0.05));
    muelle.receiveShadow = true;
    agregar("mar", muelle);
    muelles.push([x, largo]);
  }

  // Yates: casco con proa en punta, cubiertas y franja de ventanas (geometría por vértices)
  const yate = (() => {
    const M = new Malla(), blanco = new THREE.Color(0xf7f7f5), azul = new THREE.Color(0x14213d), vid = new THREE.Color(0x111a24);
    const perfil = [[-7, -1.6], [4, -1.8], [7.5, 0], [4, 1.8], [-7, 1.6]];   // vista superior
    const nivel = (h, esc) => perfil.map(([a, b]) => new THREE.Vector3(a * esc, h, b * esc));
    const quillas = [nivel(-0.6, 0.82), nivel(0.6, 1), nivel(1.6, 1)];
    for (let k = 0; k < 2; k++) {
      const abajo = quillas[k], arriba = quillas[k + 1];
      for (let i = 0; i < perfil.length; i++) {
        const j = (i + 1) % perfil.length, mid = abajo[i].clone().add(abajo[j]).multiplyScalar(0.5);
        M.quad(abajo[i], abajo[j], arriba[j], arriba[i], [[0, 0], [1, 0], [1, 1], [0, 1]], k === 1 ? blanco : azul, mid.setY(0));
      }
    }
    const cub = quillas[2];
    M.tri(cub[0], cub[1], cub[2], [[0, 0], [1, 0], [1, 1]], blanco, ARRIBA);
    M.tri(cub[0], cub[2], cub[3], [[0, 0], [1, 0], [1, 1]], blanco, ARRIBA);
    M.tri(cub[0], cub[3], cub[4], [[0, 0], [1, 0], [1, 1]], blanco, ARRIBA);
    const caja = (x0, x1, z, h0, h1, col) => {
      const p = (x, y, zz) => new THREE.Vector3(x, y, zz);
      const c = [p(x0, h0, -z), p(x1, h0, -z), p(x1, h0, z), p(x0, h0, z)], t = c.map((v) => v.clone().setY(h1));
      for (let i = 0; i < 4; i++) {
        const j = (i + 1) % 4, mid = c[i].clone().add(c[j]).multiplyScalar(0.5).setY(0);
        M.quad(c[i], c[j], t[j], t[i], [[0, 0], [1, 0], [1, 1], [0, 1]], col, mid);
      }
      M.quad(t[0], t[1], t[2], t[3], [[0, 0], [1, 0], [1, 1], [0, 1]], blanco, ARRIBA);
    };
    caja(-5, 2.5, 1.35, 1.6, 2.1, blanco); caja(-5, 2.5, 1.36, 2.1, 2.7, vid);
    caja(-4, 1, 1.1, 2.7, 3.2, blanco); caja(-4, 1, 1.11, 3.2, 3.7, vid); caja(-3.5, 0, 0.9, 3.7, 4.0, blanco);
    return M.geometria();
  })();
  const lugaresYate = [];
  for (const [x, largo] of muelles) {
    for (let k = 0; k < largo / 6.5; k++) for (const lado of [1, -1]) {
      if (rnd() < 0.2) continue;
      lugaresYate.push([x + lado * (7 + rnd()), ORILLA - 12 - k * 6.5, lado > 0 ? 0 : Math.PI, 0.55 + rnd() * 0.25]);
    }
  }
  for (let i = 0; i < 30; i++) lugaresYate.push([-MX * 1.5 + rnd() * MX * 3, ORILLA - 170 - rnd() * 260, rnd() * 6.3, 0.8 + rnd() * 0.9]);
  const matYate = new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.25, metalness: 0.1, clearcoat: 1 });
  const iYate = new THREE.InstancedMesh(yate, matYate, lugaresYate.length);
  lugaresYate.forEach(([x, y, rot, esc], i) => {
    q.setFromAxisAngle(ARRIBA, rot + Math.PI / 2);
    m.compose(P(x, y, -0.15), q, e.set(esc, esc, esc));
    iYate.setMatrixAt(i, m);
  });
  iYate.castShadow = iYate.receiveShadow = true;
  agregar("mar", iYate);
  // Mástiles de algunos veleros
  const mastiles = lugaresYate.filter(() => rnd() < 0.3);
  const iMastil = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.06, 0.08, 14, 5), new THREE.MeshStandardMaterial({ color: 0xe5e7eb, metalness: 0.6, roughness: 0.3 }), mastiles.length);
  mastiles.forEach(([x, y, , esc], i) => { m.compose(P(x, y, 8 * esc), q.identity(), e.set(esc, esc, esc)); iMastil.setMatrixAt(i, m); });
  agregar("mar", iMastil);

  // ---------------------------------------------------------------- suelo de la ciudad (adoquín)
  const matSuelo = new THREE.MeshStandardMaterial({ color: 0xa79d90, roughness: 0.95 });
  pbr(matSuelo, "brick_pavement_02", { repetir: [700, 350], relieve: 0.8 });
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(3000, 1500), matSuelo);
  suelo.rotation.x = -Math.PI / 2;
  suelo.position.set(0, -0.05, -(ORILLA + 750));
  suelo.receiveShadow = true;
  agregar("suelo", suelo);

  // ---------------------------------------------------------------- colinas (relieve con bosque)
  const Y0 = MY + 110;                              // donde empiezan a subir
  const alturaColina = (x, y) => {
    if (y < Y0) return 0;
    const r = THREE.MathUtils.smoothstep(y - Y0, 0, 320);
    return r * (70 + 140 * fbm(x * 0.004 + 3, y * 0.004)) + r * 18 * fbm(x * 0.03, y * 0.03);
  };
  {
    const ancho = 2600, fondo = 900, nx = 220, ny = 90;
    const g = new THREE.PlaneGeometry(ancho, fondo, nx, ny);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position, col = [];
    const c1 = new THREE.Color(0x4f6b34), c2 = new THREE.Color(0x2f4a24), roca = new THREE.Color(0x9b8f7c);
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = Y0 - 15 + fondo / 2 - p.getZ(i);   // three z = -y
      p.setZ(i, -y);
      const h = alturaColina(x, y);
      p.setY(i, h - 0.2);
      const f = fbm(x * 0.02, y * 0.02, 3);
      color.copy(c1).lerp(c2, f).lerp(roca, THREE.MathUtils.smoothstep(h, 150, 230) * 0.7);
      col.push(color.r, color.g, color.b);
    }
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.computeVertexNormals();
    const colinas = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 }));
    colinas.receiveShadow = true;
    agregar("colinas", colinas);
  }

  // ---------------------------------------------------------------- ciudad
  const paleta = [0xf3e3c3, 0xeccb9a, 0xe7b48f, 0xf6dfc0, 0xefe6d6, 0xd99a7a, 0xf8f2e6, 0xe4c58f, 0xf2c9b8, 0xfff4d6];
  const edificios = [], parque = [], palmeras = [], pinos = [];
  // Tramos de pista con graderías (s en metros): ahí no van palmeras ni faroles
  const tramos = [[0, 140], [150, 215], [380, 440], [520, 600], [880, 960], [1000, pista.largo]];
  const enTramo = (s) => tramos.some(([a, b]) => s >= a && s <= b);
  const paso = 13;
  for (let x = -MX - 90; x <= MX + 90; x += paso) {
    for (let y = ORILLA + 14; y <= Y0 + 30; y += paso) {
      const jx = x + (rnd() - 0.5) * 2, jy = y + (rnd() - 0.5) * 2;
      const [d, sd] = dist(jx, jy);
      if (d < muro + 7) continue;
      if (dentro(jx, jy)) {
        if (d > muro + 14 && rnd() < 0.1) edificios.push([jx, jy, 9 + rnd() * 3, 9 + rnd() * 3, 2 + Math.floor(rnd() * 3), 0]);
        else parque.push([jx, jy]);
        continue;
      }
      if (d < muro + 15) {                          // bulevar junto a la pista: palmeras
        if (rnd() < 0.35 && !enTramo(sd)) palmeras.push([jx, jy]);
        continue;
      }
      if (rnd() < 0.1) continue;                    // plazas
      const lejos = Math.min(1, Math.max(0, d - 25) / 180);
      const pisos = 3 + Math.floor(rnd() * 4 + lejos * rnd() * 14);
      edificios.push([jx, jy, 9 + rnd() * 3, 9 + rnd() * 3, pisos, 0]);
    }
  }
  // Villas en las colinas
  for (let i = 0; i < 260; i++) {
    const x = (rnd() * 2 - 1) * 900, y = Y0 + 20 + rnd() * 260;
    const h = alturaColina(x, y);
    if (h > 3) edificios.push([x, y, 8 + rnd() * 5, 8 + rnd() * 5, 1 + Math.floor(rnd() * 3), h - 1]);
  }
  for (let i = 0; i < 1000; i++) {                  // bosque en las colinas
    const x = (rnd() * 2 - 1) * 1250, y = Y0 + 15 + rnd() * 700;
    const h = alturaColina(x, y);
    if (h > 2) pinos.push([x, y, h, 1.2 + rnd() * 1.4]);
  }
  for (const [x, y] of parque) {                    // jardines del circuito
    if (rnd() < 0.55) pinos.push([x + (rnd() - 0.5) * 8, y + (rnd() - 0.5) * 8, 0, 0.8 + rnd() * 0.5]);
    if (rnd() < 0.35) palmeras.push([x + (rnd() - 0.5) * 8, y + (rnd() - 0.5) * 8]);
  }

  // Césped del parque interior
  const formaParque = new THREE.Shape(pista.centro.filter((_, i) => i % 6 === 0).map(([, x, y]) => new THREE.Vector2(x, y)));
  const gParque = new THREE.ShapeGeometry(formaParque);
  { const p = gParque.attributes.position, uv = gParque.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / 4, p.getY(i) / 4); }
  const matParque = new THREE.MeshStandardMaterial({ color: 0x5f8f3e, roughness: 1 });
  // La foto del pasto sale seca con la luz del atardecer: se tiñe a un verde de jardín cuidado
  pbr(matParque, "leafy_grass", { repetir: [1, 1] }).then((mat) => mat.color.set(0xa9d68c));
  const cesped = new THREE.Mesh(gParque, matParque);
  cesped.rotation.x = -Math.PI / 2;
  cesped.position.y = -0.02;
  cesped.receiveShadow = true;
  agregar("ciudad", cesped);

  // Edificios: muros con fachada (u = ancho/vano, v = pisos), cornisa y azotea
  const PISO = 3.2;
  const lisoUV = [[0.04, 0.97], [0.05, 0.97], [0.05, 0.98], [0.04, 0.98]];   // zona de estuco sin ventanas
  const BLOQUE = 120, bloques = new Map(), techosTeja = new Malla();
  const mallaDe = (x, y, k) => {
    const clave = `${Math.floor(x / BLOQUE)},${Math.floor(y / BLOQUE)},${k}`;
    if (!bloques.has(clave)) bloques.set(clave, new Malla());
    return bloques.get(clave);
  };
  // Tipos de fachada: 0 y 1 mediterráneas (persianas verdes o azules), 2 torre moderna
  // de vidrio con balcones corridos (el skyline de Mónaco), 3 locales comerciales
  const torres = [0xf6f3ec, 0xebe6dc, 0xe2e6ea, 0xf3e9d8, 0xfaf8f4];
  const blanco = new THREE.Color(1, 1, 1), azoteas = [];
  for (const [x, y, lx, ly, pisos, base] of edificios) {
    const torre = pisos >= 9;
    const M = mallaDe(x, y, torre ? 2 : rnd() < 0.55 ? 0 : 1);
    const conTienda = !torre && base === 0 && pisos >= 3 && dist(x, y)[0] < muro + 45;
    const T = conTienda ? mallaDe(x, y, 3) : null, p0 = conTienda ? 1 : 0;   // pisos con locales
    const h = pisos * PISO, col = color.setHex(torre ? torres[Math.floor(rnd() * torres.length)] : paleta[Math.floor(rnd() * paleta.length)]).clone();
    const esq = [[x - lx / 2, y - ly / 2], [x + lx / 2, y - ly / 2], [x + lx / 2, y + ly / 2], [x - lx / 2, y + ly / 2]];
    for (let i = 0; i < 4; i++) {
      const [ax, ay] = esq[i], [bx, by] = esq[(i + 1) % 4];
      const largo = Math.hypot(bx - ax, by - ay), fuera = P((ax + bx) / 2 - x, (ay + by) / 2 - y, 0);
      const vanos = Math.max(1, Math.round(largo / VANO));
      if (T) {
        const u0 = Math.floor(rnd() * 4) / 4;           // cada vano muestra un local distinto
        T.quad(P(ax, ay, base), P(bx, by, base), P(bx, by, base + PISO), P(ax, ay, base + PISO),
          [[u0, 0], [u0 + vanos / 4, 0], [u0 + vanos / 4, 1], [u0, 1]], blanco, fuera);
      }
      M.quad(P(ax, ay, base + p0 * PISO), P(bx, by, base + p0 * PISO), P(bx, by, base + h), P(ax, ay, base + h),
        [[0, p0], [vanos, p0], [vanos, pisos], [0, pisos]], col, fuera);
      // Cornisa saliente
      const o = 0.35, cx0 = ax + Math.sign(ax - x) * o, cy0 = ay + Math.sign(ay - y) * o, cx1 = bx + Math.sign(bx - x) * o, cy1 = by + Math.sign(by - y) * o;
      const oscuro = col.clone().multiplyScalar(0.88);
      M.quad(P(cx0, cy0, base + h), P(cx1, cy1, base + h), P(cx1, cy1, base + h + 0.55), P(cx0, cy0, base + h + 0.55), lisoUV, oscuro, fuera);
    }
    const o = 0.35;
    const ti = esq.map(([ex, ey]) => P(ex + Math.sign(ex - x) * o, ey + Math.sign(ey - y) * o, base + h + 0.55));
    if (!torre && rnd() < 0.45) {                   // techo de teja a cuatro aguas
      const cima = P(x, y, base + h + 0.55 + Math.min(lx, ly) * 0.32);
      for (let i = 0; i < 4; i++) {
        const a = ti[i], b = ti[(i + 1) % 4];
        const fuera = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5).sub(cima).setY(0.5);
        techosTeja.tri(a, b, cima, [[a.x / 3, a.z / 3], [b.x / 3, b.z / 3], [cima.x / 3, cima.z / 3]], new THREE.Color(1, 1, 1), fuera);
      }
    } else {
      M.quad(ti[0], ti[1], ti[2], ti[3], lisoUV, col.clone().multiplyScalar(0.8), ARRIBA);
      // Azotea: aires acondicionados, tanques y salidas de escalera
      const n = torre ? 3 + Math.floor(rnd() * 3) : Math.floor(rnd() * 3);
      for (let k = 0; k < n; k++) {
        const tipo = rnd(), [sx, sy, sz] = tipo < 0.55 ? [1.3, 0.9, 1.0] : tipo < 0.8 ? [1.6, 1.8, 1.6] : [2.6, 2.4, 2.2];
        azoteas.push([x + (rnd() - 0.5) * (lx - 3), y + (rnd() - 0.5) * (ly - 3), base + h + 0.55, sx, sy, sz, tipo]);
      }
    }
  }
  if (azoteas.length) {
    const iAz = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0),
      new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0.3 }), azoteas.length);
    azoteas.forEach(([ax, ay, az, sx, sy, sz, tipo], i) => {
      q.setFromAxisAngle(ARRIBA, Math.floor(rnd() * 4) * Math.PI / 2);
      m.compose(P(ax, ay, az), q, e.set(sx, sy, sz)); iAz.setMatrixAt(i, m);
      iAz.setColorAt(i, color.setHex(tipo < 0.55 ? 0xc9ccd1 : tipo < 0.8 ? 0x9aa3ad : 0xe8e2d6));
    });
    iAz.castShadow = iAz.receiveShadow = true;
    agregar("ciudad", iAz);
  }
  const torreTex = texturaTorre(), tiendasTex = texturaTiendas();
  const matFachadas = [texturaFachada("#47704f"), texturaFachada("#3f5f86")].map((map) =>
    new THREE.MeshStandardMaterial({ map, vertexColors: true, roughness: 0.85 }));
  matFachadas.push(new THREE.MeshStandardMaterial({ map: torreTex.map, roughnessMap: torreTex.rugosidad,
    vertexColors: true, roughness: 1, metalness: 0.25 }));
  matFachadas.push(new THREE.MeshStandardMaterial({ map: tiendasTex.map, roughnessMap: tiendasTex.rugosidad, roughness: 1, metalness: 0.15 }));
  const matTeja = new THREE.MeshStandardMaterial({ color: 0xb4583a, roughness: 0.8 });
  pbr(matTeja, "clay_roof_tiles", { repetir: [1, 1] });
  for (const [clave, M] of bloques) {
    const edif = new THREE.Mesh(M.geometria(), matFachadas[+clave.split(",")[2]]);
    edif.castShadow = edif.receiveShadow = true;
    agregar("ciudad", edif);
  }
  const teja = new THREE.Mesh(techosTeja.geometria(), matTeja);
  teja.castShadow = teja.receiveShadow = true;
  agregar("ciudad", teja);

  // ---------------------------------------------------------------- árboles
  // Palmera: tronco curvo con anillos + corona de hojas curvadas
  const troncoPalmera = new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0, 0), new THREE.Vector3(0.3, 3, 0), new THREE.Vector3(0.9, 6, 0), new THREE.Vector3(1.6, 8.5, 0)]), 16, 0.22, 7);
  const corona = (() => {
    const hojas = [];
    for (let k = 0; k < 11; k++) {
      const g = new THREE.PlaneGeometry(1.1, 4.2, 1, 8);
      const p = g.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const t = (p.getY(i) + 2.1) / 4.2;              // 0 base, 1 punta
        p.setXYZ(i, p.getX(i) * (0.35 + 0.65 * Math.sin(t * Math.PI)), t * 4.2, -Math.pow(t, 1.8) * 2.6);
      }
      g.rotateX(-Math.PI / 2 + 0.55 + rnd() * 0.25);
      g.rotateY((k / 11) * Math.PI * 2 + rnd() * 0.3);
      hojas.push(g);
    }
    const g = mergeGeometries(hojas);
    g.computeVertexNormals();
    return g;
  })();
  const matHoja = new THREE.MeshStandardMaterial({ map: texturaHoja(), alphaTest: 0.35, side: THREE.DoubleSide, roughness: 0.7 });
  const matCorteza = new THREE.MeshStandardMaterial({ map: texturaCorteza(), roughness: 0.95 });
  const iTroncoP = new THREE.InstancedMesh(troncoPalmera, matCorteza, palmeras.length);
  const iCorona = new THREE.InstancedMesh(corona, matHoja, palmeras.length);
  palmeras.forEach(([x, y], i) => {
    const esc = 0.85 + rnd() * 0.4;
    q.setFromAxisAngle(ARRIBA, rnd() * Math.PI * 2);
    m.compose(P(x, y, 0), q, e.set(esc, esc, esc)); iTroncoP.setMatrixAt(i, m);
    const punta = new THREE.Vector3(1.6, 8.5, 0).multiplyScalar(esc).applyQuaternion(q).add(P(x, y, 0));
    m.compose(punta, q, e.set(esc, esc, esc)); iCorona.setMatrixAt(i, m);
  });
  iTroncoP.castShadow = iCorona.castShadow = true;
  agregar("arboles", iTroncoP, iCorona);

  // Pino piñonero: tronco con ramas + copa ancha y aplanada hecha de "tarjetas" de agujas
  // (planos con transparencia, como en los juegos de carreras). Las normales salen del
  // centro de la copa: así la luz la sombrea como un volumen suave y no como láminas.
  const copaPino = (densidad) => {
    const partes = [];
    const masas = [[0, 0, 0, 3.3, 1.35], [1.9, -0.25, 0.9, 2.5, 1.1], [-1.7, -0.15, -1.0, 2.6, 1.1], [0.4, 0.35, -1.9, 2.3, 1.0]];
    for (const [dx, dy, dz, r, ry] of masas) {
      const n = Math.round(r * densidad);
      for (let i = 0; i < n; i++) {
        const v = new THREE.Vector3();
        do v.set(rnd() * 2 - 1, rnd() * 2 - 1, rnd() * 2 - 1); while (v.lengthSq() > 1);
        v.normalize().multiplyScalar(0.5 + 0.5 * Math.cbrt(rnd()));
        if (v.y < -0.35) v.y = -0.35 - (v.y + 0.35) * 0.3;            // copa plana por debajo
        const tam = 1.5 + rnd() * 0.9;
        const g = new THREE.PlaneGeometry(tam, tam * (0.75 + rnd() * 0.3)).toNonIndexed();
        g.rotateZ(rnd() * Math.PI * 2); g.rotateX(-Math.PI / 2 + (rnd() - 0.5) * 1.6); g.rotateY(rnd() * Math.PI * 2);
        g.translate(v.x * r + dx, v.y * ry + dy, v.z * r + dz);
        const p = g.attributes.position, nr = g.attributes.normal;
        for (let k = 0; k < p.count; k++) {
          const w = new THREE.Vector3((p.getX(k) - dx) / r, (p.getY(k) - dy) / ry + 0.35, (p.getZ(k) - dz) / r).normalize();
          nr.setXYZ(k, w.x, w.y, w.z);
        }
        partes.push(g);
      }
      // Núcleo oscuro (hojas en sombra): tapa los huecos entre tarjetas
      const nucleo = new THREE.IcosahedronGeometry(1, 1);
      nucleo.scale(r * 0.42, ry * 0.4, r * 0.42); nucleo.translate(dx, dy - 0.1, dz);
      const uv = nucleo.attributes.uv;
      for (let k = 0; k < uv.count; k++) uv.setXY(k, 0.5, 0.5);
      partes.push(nucleo);
    }
    return mergeGeometries(partes);
  };
  const troncoPino = (() => {
    const partes = [new THREE.CylinderGeometry(0.2, 0.34, 6.4, 7).translate(0, 3.2, 0)];
    for (let k = 0; k < 4; k++) {                    // ramas principales hacia la copa
      const g = new THREE.CylinderGeometry(0.07, 0.13, 2.6, 5);
      g.translate(0, 1.3, 0); g.rotateZ(0.75 + rnd() * 0.25); g.rotateY((k / 4) * Math.PI * 2 + rnd() * 0.5);
      g.translate(0, 4.6 + rnd() * 0.8, 0);
      partes.push(g);
    }
    return mergeGeometries(partes);
  })();
  const matAgujas = new THREE.MeshStandardMaterial({ map: texturaAgujas(), alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.85 });
  // Con DoubleSide three voltea la normal de las caras vistas por detrás; aquí las normales ya
  // salen del centro de la copa, así que no se voltean (si no, salen manchas oscuras)
  matAgujas.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace("#include <normal_fragment_begin>",
      THREE.ShaderChunk.normal_fragment_begin.replace("normal *= faceDirection;", ""));
  };
  // Dos niveles de detalle: pinos del parque (junto a la pista, con sombra) y bosque de las
  // colinas (menos tarjetas y sin sombra: su caja cubre kilómetros y entraría entera al mapa de sombras)
  for (const [lista, densidad, sombra] of [[pinos.filter((p) => p[2] === 0), 13, true], [pinos.filter((p) => p[2] !== 0), 5, false]]) {
    if (!lista.length) continue;
    const iTroncoN = new THREE.InstancedMesh(troncoPino, matCorteza, lista.length);
    const iCopa = new THREE.InstancedMesh(copaPino(densidad), matAgujas, lista.length);
    lista.forEach(([x, y, h, esc], i) => {
      q.setFromAxisAngle(ARRIBA, rnd() * Math.PI * 2);
      m.compose(P(x, y, h), q, e.set(esc, esc, esc)); iTroncoN.setMatrixAt(i, m);
      m.compose(P(x, y, h + 6.6 * esc), q, e.set(esc, esc, esc)); iCopa.setMatrixAt(i, m);
      iCopa.setColorAt(i, color.setHSL(0.22 + rnd() * 0.07, 0.35 + rnd() * 0.25, 0.75 + rnd() * 0.25));
    });
    iTroncoN.castShadow = iCopa.castShadow = sombra;
    iTroncoN.receiveShadow = iCopa.receiveShadow = sombra;
    agregar("arboles", iTroncoN, iCopa);
  }

  // ---------------------------------------------------------------- público en graderías
  // Graderías de 5 filas con asientos de color, muro trasero y, en la recta de meta,
  // techo con marquesina. El público está de pie, cada persona con su ropa, piel y pelo.
  const personas = [], banderas = [], gradas = new Malla(), marquesina = new Malla();
  const FILAS = 5, FONDO = 0.85, ESCALON = 0.42, TECHO = ESCALON * FILAS + 3.4;
  const gris = new THREE.Color(0xa3a7ad), muroGrada = new THREE.Color(0x8d939b), techoCol = new THREE.Color(0xe8eaed);
  const asientos = [0x1d4ed8, 0xb91c1c, 0x0f766e, 0x1e3a8a, 0x7e22ce, 0xb91c1c].map((h) => new THREE.Color(h));
  const columnas = [];
  for (let k = 0; k < pista.centro.length - 2; k += 2) {
    const [s, x, y, h] = pista.centro[k], [s2, x2, y2, h2] = pista.centro[k + 2];
    if (!enTramo(s)) continue;
    const tramo = tramos.findIndex(([a, b]) => s >= a && s <= b);
    const conTecho = tramo === 0 || tramo === tramos.length - 1;
    for (const lado of [1, -1]) {
      const libre = (off) => {
        const px = x - Math.sin(h) * off, py = y + Math.cos(h) * off;
        const [, sd] = dist(px, py);
        return py > ORILLA + 1 && !(Math.abs(sd - s) > 30 && Math.abs(sd - s) < pista.largo - 30);
      };
      if (!libre(lado * (muro + 1 + FILAS * FONDO))) continue;
      const pt = (xx, yy, hh, off, z) => P(xx - Math.sin(hh) * off, yy + Math.cos(hh) * off, z);
      const frente = new THREE.Vector3(Math.sin(h) * lado, 0, Math.cos(h) * lado);   // hacia la pista
      const uvq = [[0, 0], [1, 0], [1, 1], [0, 1]];
      for (let fila = 0; fila < FILAS; fila++) {
        const o0 = lado * (muro + 0.9 + fila * FONDO), o1 = lado * (muro + 0.9 + (fila + 1) * FONDO), alto = ESCALON * (fila + 1);
        gradas.quad(pt(x, y, h, o0, alto), pt(x2, y2, h2, o0, alto), pt(x2, y2, h2, o1, alto), pt(x, y, h, o1, alto), uvq, gris, ARRIBA);
        // Contrahuella del escalón = respaldo de los asientos (de color)
        gradas.quad(pt(x, y, h, o0, alto - ESCALON), pt(x2, y2, h2, o0, alto - ESCALON), pt(x2, y2, h2, o0, alto), pt(x, y, h, o0, alto), uvq, asientos[tramo % asientos.length], frente);
        if (rnd() > 0.78) continue;                  // algunos puestos vacíos
        const t = 0.15 + rnd() * 0.7, off = lado * (muro + 0.9 + fila * FONDO + FONDO * (0.45 + rnd() * 0.2));
        const px = x + (x2 - x) * t - Math.sin(h) * off, py = y + (y2 - y) * t + Math.cos(h) * off;
        // El modelo mira hacia +x: se gira para que mire a la pista
        personas.push([px, py, alto, h + (lado > 0 ? -Math.PI / 2 : Math.PI / 2) + (rnd() - 0.5) * 0.5, rnd() < 0.25, tramo]);
        if (fila === FILAS - 1 && rnd() < 0.04) banderas.push([px, py, h, alto]);
      }
      // Muro trasero
      const ob = lado * (muro + 0.9 + FILAS * FONDO);
      gradas.quad(pt(x, y, h, ob, 0), pt(x2, y2, h2, ob, 0), pt(x2, y2, h2, ob, ESCALON * FILAS + 1.1), pt(x, y, h, ob, ESCALON * FILAS + 1.1), uvq, muroGrada, frente);
      if (conTecho) {
        // Del lado derecho la pista avanza hacia la izquierda de quien mira: u al revés
        const oa = lado * (muro + 0.6), u0 = lado * s / 24, u1 = lado * s2 / 24;
        gradas.quad(pt(x, y, h, oa, TECHO), pt(x2, y2, h2, oa, TECHO), pt(x2, y2, h2, ob, TECHO + 0.6), pt(x, y, h, ob, TECHO + 0.6), uvq, techoCol, ARRIBA.clone().negate());
        // Marquesina con publicidad en el borde del techo, mirando a la pista
        marquesina.quad(pt(x, y, h, oa, TECHO - 0.9), pt(x2, y2, h2, oa, TECHO - 0.9), pt(x2, y2, h2, oa, TECHO + 0.05), pt(x, y, h, oa, TECHO + 0.05),
          [[u0, 0], [u1, 0], [u1, 1], [u0, 1]], techoCol, frente);
        if (k % 16 === 0) columnas.push(pt(x, y, h, ob - lado * 0.2, 0));
      }
    }
  }
  const matGrada = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide });
  pbr(matGrada, "grey_plaster", { repetir: [1, 1], rugosidad: false });
  const grada = new THREE.Mesh(gradas.geometria(), matGrada);
  grada.receiveShadow = grada.castShadow = true;
  agregar("publico", grada);
  const fascia = new THREE.Mesh(marquesina.geometria(), new THREE.MeshStandardMaterial({ map: texturaMarquesina(), roughness: 0.5 }));
  agregar("publico", fascia);
  if (columnas.length) {
    const iCol = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.12, 0.12, TECHO + 0.6, 8).translate(0, (TECHO + 0.6) / 2, 0),
      new THREE.MeshStandardMaterial({ color: 0xd1d5db, metalness: 0.7, roughness: 0.35 }), columnas.length);
    columnas.forEach((p, i) => iCol.setMatrixAt(i, m.makeTranslation(p.x, p.y, p.z)));
    iCol.castShadow = true;
    agregar("publico", iCol);
  }

  // Persona (de frente hacia +x, pies en y = 0). Cada pieza dice qué es (atributo "parte")
  // y el shader le pone el color de esa persona: piel, camiseta, pantalón, pelo o zapatos.
  const PIEL = 0, CAMISA = 1, PANTALON = 2, PELO = 3, ZAPATO = 4;
  const cuerpoPersona = (brazosArriba) => {
    const partes = [];
    const pieza = (g, parte, x, y, z, rx = 0, esc = null) => {
      if (esc) g.scale(...esc);
      g.rotateX(rx); g.translate(x, y, z);
      g.deleteAttribute("uv");
      g.setAttribute("parte", new THREE.Float32BufferAttribute(new Array(g.attributes.position.count).fill(parte), 1));
      partes.push(g);
    };
    for (const z of [0.1, -0.1]) {
      pieza(new THREE.BoxGeometry(0.25, 0.07, 0.1), ZAPATO, 0.04, 0.035, z);
      pieza(new THREE.CylinderGeometry(0.07, 0.056, 0.82, 6, 1, true), PANTALON, 0, 0.48, z);
    }
    pieza(new THREE.CylinderGeometry(0.17, 0.165, 0.2, 8, 1, true), PANTALON, 0, 0.93, 0, 0, [0.62, 1, 1]);
    pieza(new THREE.CylinderGeometry(0.2, 0.165, 0.56, 8), CAMISA, 0, 1.3, 0, 0, [0.6, 1, 1]);
    pieza(new THREE.SphereGeometry(0.2, 8, 3, 0, Math.PI * 2, 0, Math.PI / 2), CAMISA, 0, 1.56, 0, 0, [0.6, 0.35, 1]);   // hombros
    pieza(new THREE.CylinderGeometry(0.05, 0.056, 0.1, 6), PIEL, 0, 1.62, 0);
    pieza(new THREE.SphereGeometry(0.105, 8, 6), PIEL, 0.012, 1.75, 0, 0, [1, 1.15, 0.9]);
    // Pelo: casquete corrido hacia atrás (deja la cara libre)
    pieza(new THREE.SphereGeometry(0.113, 8, 4, 0, Math.PI * 2, 0, Math.PI * 0.5), PELO, -0.03, 1.79, 0, 0, [1, 1.05, 0.95]);
    pieza(new THREE.SphereGeometry(0.022, 4, 3), PIEL, 0.115, 1.74, 0);                                                  // nariz
    for (const lado of [1, -1]) {
      const a = brazosArriba ? 0.3 : 0.09;
      const dir = new THREE.Vector3(0, brazosArriba ? Math.cos(a) : -Math.cos(a), lado * Math.sin(a));
      const rx = brazosArriba ? lado * a : -lado * a, hombro = new THREE.Vector3(0, 1.52, lado * 0.205);
      const en = (d) => hombro.clone().addScaledVector(dir, d);
      let c = en(0.15); pieza(new THREE.CylinderGeometry(0.056, 0.048, 0.3, 6, 1, true), CAMISA, c.x, c.y, c.z, rx);
      c = en(0.44); pieza(new THREE.CylinderGeometry(0.044, 0.036, 0.29, 6, 1, true), PIEL, c.x, c.y, c.z, rx);
      c = en(0.63); pieza(new THREE.SphereGeometry(0.046, 5, 4), PIEL, c.x, c.y, c.z, 0, [0.8, 1.2, 1]);
    }
    return mergeGeometries(partes);
  };
  // Colores realistas de un público de carreras (hinchas de rojo, mucha ropa oscura y clara)
  const camisas = [0xb3171d, 0xb3171d, 0xc81e1e, 0xf2f1ec, 0xf2f1ec, 0x1c2638, 0x18181b, 0x18181b, 0x8b9097, 0x86a9cf,
    0xe0702a, 0x24707f, 0xcfa83a, 0x2e5638, 0xcf8ea2, 0xcbb995, 0x5b2a86, 0x0e4c92];
  const pantalones = [0x34466b, 0x283550, 0x1d1d21, 0x1d1d21, 0xa89a78, 0xdcd7cc, 0x575c64, 0x3e4a33];
  const pieles = [0xf1cdb0, 0xe6b591, 0xd09a74, 0xa86f4c, 0x6e452e, 0xf6dcc7, 0xc68a64];
  const pelos = [0x1d1814, 0x2f2219, 0x5a3c22, 0x8a6a42, 0xc7a978, 0x8e8b88, 0x0e0e0f, 0x1d1814];
  const gorras = [0xc81e1e, 0xf2f1ec, 0x1c2638, 0x18181b, 0xe0702a];
  const tiempoGPU = { value: 0 };
  const matPublico = (saluda) => {
    const mat = new THREE.MeshStandardMaterial({ roughness: 0.82 });
    mat.onBeforeCompile = (sh) => {
      sh.uniforms.uTiempo = tiempoGPU;
      sh.vertexShader = `uniform float uTiempo;
attribute float parte;
attribute vec3 aCamisa;
attribute vec3 aPantalon;
attribute vec3 aPiel;
attribute vec3 aPelo;
varying vec3 vTinte;
` + sh.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
  vTinte = parte < 0.5 ? aPiel : parte < 1.5 ? aCamisa : parte < 2.5 ? aPantalon : parte < 3.5 ? aPelo : vec3(0.03);
  float fase = float(gl_InstanceID) * 1.7;
  ${saluda ? "transformed.y += max(0.0, sin(uTiempo * 7.0 + fase)) * 0.12;"
    : "transformed.z += sin(uTiempo * 1.3 + fase) * 0.02 * position.y;"}`);
      sh.fragmentShader = "varying vec3 vTinte;\n" + sh.fragmentShader.replace(
        "vec4 diffuseColor = vec4( diffuse, opacity );", "vec4 diffuseColor = vec4( diffuse * vTinte, opacity );");
    };
    mat.customProgramCacheKey = () => "publico-" + saluda;
    return mat;
  };
  const cuerpos = [cuerpoPersona(false), cuerpoPersona(true)];
  const mats = [matPublico(false), matPublico(true)];
  const elegir = (lista) => lista[Math.floor(rnd() * lista.length)];
  // Un grupo por tramo de pista y por postura: la tarjeta gráfica solo dibuja las graderías en cámara
  for (let tr = 0; tr < tramos.length; tr++) for (const arriba of [false, true]) {
    const lista = personas.filter((p) => p[4] === arriba && p[5] === tr);
    if (!lista.length) continue;
    const geo = cuerpos[+arriba].clone(), n = lista.length;
    const attr = (nombre) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3); geo.setAttribute(nombre, a); return a; };
    const [aCam, aPan, aPie, aPel] = ["aCamisa", "aPantalon", "aPiel", "aPelo"].map(attr);
    const im = new THREE.InstancedMesh(geo, mats[+arriba], n);
    lista.forEach(([x, y, z, rot], i) => {
      q.setFromAxisAngle(ARRIBA, rot);
      const alto = 0.92 + rnd() * 0.16, ancho = 0.92 + rnd() * 0.2;
      m.compose(P(x, y, z), q, e.set(ancho, alto, ancho)); im.setMatrixAt(i, m);
      color.setHex(elegir(camisas)); aCam.setXYZ(i, color.r, color.g, color.b);
      color.setHex(elegir(pantalones)); aPan.setXYZ(i, color.r, color.g, color.b);
      color.setHex(elegir(pieles)); aPie.setXYZ(i, color.r, color.g, color.b);
      color.setHex(rnd() < 0.18 ? elegir(gorras) : elegir(pelos)); aPel.setXYZ(i, color.r, color.g, color.b);
    });
    im.computeBoundingSphere();   // para descartar lo que no se ve
    im.receiveShadow = true;
    agregar("publico", im);
  }
  console.info(`Público: ${personas.length} personas`);

  const flagsMat = [texturaBandera(["#e11d48", "#f8fafc"]), texturaBandera(["#f8fafc", "#2563eb", "#e11d48"]),
    texturaBandera(["#16a34a", "#f8fafc", "#e11d48"]), texturaBandera(["#111827", "#facc15", "#e11d48"])]
    .map((t) => new THREE.MeshStandardMaterial({ map: t, side: THREE.DoubleSide, roughness: 0.8 }));
  const grupoBanderas = new THREE.Group();
  const matPalo = new THREE.MeshStandardMaterial({ color: 0x9ca3af, metalness: 0.6, roughness: 0.4 });
  banderas.forEach(([x, y, h, alto], i) => {
    const g = new THREE.Group();
    g.position.copy(P(x, y, alto));
    g.rotation.y = h;
    const palo = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.6, 5), matPalo);
    palo.position.y = 1.8;
    const tela = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.72, 10, 1), flagsMat[i % flagsMat.length]);
    tela.position.set(0.55, 2.7, 0);
    g.add(palo, tela);
    g.userData.tela = tela;
    g.userData.fase = rnd() * 6;
    grupoBanderas.add(g);
  });
  agregar("publico", grupoBanderas);

  // ---------------------------------------------------------------- túnel
  const tramoT = tramoTunel(pista);
  if (tramoT) {
    const [s0, s1] = tramoT;
    const grupoT = new THREE.Group();
    const matT = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, side: THREE.DoubleSide });
    pbr(matT, "grey_plaster_02", { repetir: [1, 1], rugosidad: false });
    for (const off of [-muro - 0.6, muro + 0.6]) grupoT.add(new THREE.Mesh(paredTramo(pista, P, off, 0, 6.5, s0, s1, 0xd6d3d1), matT));
    grupoT.add(new THREE.Mesh(techoTramo(pista, P, -muro - 0.6, muro + 0.6, 6.5, s0, s1, 0x9ca3af), matT));
    for (const off of [-2.5, 2.5]) {
      grupoT.add(new THREE.Mesh(techoTramo(pista, P, off - 0.15, off + 0.15, 6.45, s0, s1, 0xfff1c4),
        new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, toneMapped: false })));
    }
    grupoT.children.forEach((c) => { c.castShadow = true; c.receiveShadow = true; });
    agregar("tunel", grupoT);
  }

  // ---------------------------------------------------------------- faroles (modelo 3D de Poly Haven)
  const lugaresFarol = [];
  for (let k = 0; k < pista.centro.length; k += 70) {
    const [s, x, y, h] = pista.centro[k];
    const lado = (k / 70) % 2 ? 1 : -1, off = lado * (muro + 4.6);
    const px = x - Math.sin(h) * off, py = y + Math.cos(h) * off;
    const [d, sd] = dist(px, py);
    if (d < muro + 3 || py < ORILLA + 1 || enTramo(s) || (Math.abs(sd - s) > 30 && Math.abs(sd - s) < pista.largo - 30)) continue;
    lugaresFarol.push([px, py, h + (lado > 0 ? -Math.PI / 2 : Math.PI / 2)]);
  }
  // Poly Haven guarda las texturas del modelo en otras rutas: su API da el mapa de cada archivo
  registrar("faroles", fetch("https://api.polyhaven.com/files/street_lamp_01").then((r) => r.json())
    .then((archivos) => {
      const g = archivos.gltf["1k"].gltf, rutas = Object.fromEntries(Object.entries(g.include).map(([k, v]) => [k, v.url]));
      const gestor = new THREE.LoadingManager();
      gestor.setURLModifier((url) => { const k = Object.keys(rutas).find((r) => url.endsWith(r)); return k ? rutas[k] : url; });
      return new GLTFLoader(gestor).loadAsync(g.url);
    })
    .then((gltf) => {
      const caja = new THREE.Box3().setFromObject(gltf.scene);
      const esc = 6.5 / (caja.max.y - caja.min.y);
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const im = new THREE.InstancedMesh(o.geometry, o.material, lugaresFarol.length);
        lugaresFarol.forEach(([x, y, rot], i) => {
          q.setFromAxisAngle(ARRIBA, rot);
          m.compose(P(x, y, 0), q, e.set(esc, esc, esc)).multiply(o.matrixWorld);
          im.setMatrixAt(i, m);
        });
        im.castShadow = true;
        agregar("faroles", im);
      });
    })).catch((err) => console.warn("Faroles no disponibles", err));

  // ---------------------------------------------------------------- clima
  const luzSol = scene.getObjectByName("sol");
  function aplicarClima(mojado) {
    mojadoActual = mojado;
    const c = cielos[mojado ? "mojado" : "seco"];
    if (c) {
      scene.background = c.tex;
      scene.environment = c.env;
      scene.backgroundIntensity = mojado ? 0.6 : 0.9;
      scene.environmentIntensity = mojado ? 0.7 : 0.85;
      sol.copy(c.sol);
    } else {
      scene.background = null;
      scene.environment = envProc;
    }
    scene.fog = mojado ? new THREE.FogExp2(0x5d6670, 0.0032) : new THREE.FogExp2(0xc9a982, 0.00045);
    // AgX comprime más las luces que ACES: necesita más exposición para el mismo brillo
    renderer.toneMappingExposure = (mojado ? 0.55 : 0.7) * (renderer.toneMapping === THREE.AgXToneMapping ? 1.5 : 1);
    if (luzSol) {
      luzSol.color.set(mojado ? 0xb8c4d6 : 0xffc58a);
      luzSol.intensity = mojado ? 0.7 : 2.6;
      luzSol.userData.direccion = sol.clone().normalize();
    }
    agua.material.color.set(mojado ? 0x1c2a36 : 0x0a3550);
  }

  function actualizar(dt, t) {
    olas.offset.x += dt * 0.004; olas.offset.y += dt * 0.0025;
    for (const g of grupoBanderas.children) {
      const p = g.userData.tela.geometry.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i) + 0.55;
        p.setZ(i, Math.sin(t * 6 + g.userData.fase + x * 4) * 0.12 * x);
      }
      p.needsUpdate = true;
    }
    tiempoGPU.value = t;   // el público que saluda salta (en el shader)
  }

  aplicarClima(false);
  return { aplicarClima, actualizar };
}

// Tramo [s0, s1] de la pista bajo techo; también lo usan las cámaras de TV
export function tramoTunel(pista) {
  const tunel = pista.curvas.find((c) => c.nombre === "Túnel");
  if (!tunel) return null;
  const kt = 1 / tunel.radio;
  const idx = pista.centro.map((c, i) => [i, c]).filter(([, c]) => Math.abs(Math.abs(c[4]) - kt) < 1e-4).map(([i]) => i);
  return [pista.centro[idx[0]][0] + 8, pista.centro[idx[idx.length - 1]][0] - 8];
}

// Pared y techo solo en un tramo de la pista (para el túnel), con uv para textura
function paredTramo(pista, P, off, h0, h1, s0, s1, hex) {
  const c = pista.centro.filter((p) => p[0] >= s0 && p[0] <= s1), pos = [], col = [], uv = [];
  const k = new THREE.Color(hex);
  for (let i = 0; i < c.length - 1; i++) {
    const [sa, x, y, h] = c[i], [sb, x2, y2, h2] = c[i + 1];
    const a = P(x - Math.sin(h) * off, y + Math.cos(h) * off), b = P(x2 - Math.sin(h2) * off, y2 + Math.cos(h2) * off);
    for (const [p, hh, s] of [[a, h0, sa], [b, h0, sb], [a, h1, sa], [a, h1, sa], [b, h0, sb], [b, h1, sb]]) {
      pos.push(p.x, hh, p.z); col.push(k.r, k.g, k.b); uv.push(s / 3, hh / 3);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
}

function techoTramo(pista, P, offA, offB, alto, s0, s1, hex) {
  const c = pista.centro.filter((p) => p[0] >= s0 && p[0] <= s1), pos = [], col = [], uv = [];
  const k = new THREE.Color(hex);
  for (let i = 0; i < c.length - 1; i++) {
    const [sa, x, y, h] = c[i], [sb, x2, y2, h2] = c[i + 1];
    const pt = (xx, yy, hh, off) => P(xx - Math.sin(hh) * off, yy + Math.cos(hh) * off, alto);
    const a1 = pt(x, y, h, offA), b1 = pt(x, y, h, offB), a2 = pt(x2, y2, h2, offA), b2 = pt(x2, y2, h2, offB);
    for (const [p, s, w] of [[a1, sa, offA], [a2, sb, offA], [b1, sa, offB], [b1, sa, offB], [a2, sb, offA], [b2, sb, offB]]) {
      pos.push(p.x, p.y, p.z); col.push(k.r, k.g, k.b); uv.push(s / 3, w / 3);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
}
