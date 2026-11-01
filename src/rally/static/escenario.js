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

function texturaFollaje() {   // pino: copa con manchas de luz y sombra
  const [c, g] = lienzo(256, 256);
  g.fillStyle = "#3d5a2a"; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 3500; i++) {
    const l = 25 + Math.random() * 30;
    g.fillStyle = `hsla(${95 + Math.random() * 25},${35 + Math.random() * 20}%,${l}%,0.55)`;
    g.beginPath(); g.arc(Math.random() * 256, Math.random() * 256, 1 + Math.random() * 3.5, 0, 7); g.fill();
  }
  return aTextura(c);
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
  const paso = 13;
  for (let x = -MX - 90; x <= MX + 90; x += paso) {
    for (let y = ORILLA + 14; y <= Y0 + 30; y += paso) {
      const jx = x + (rnd() - 0.5) * 2, jy = y + (rnd() - 0.5) * 2;
      const [d] = dist(jx, jy);
      if (d < muro + 7) continue;
      if (dentro(jx, jy)) {
        if (d > muro + 14 && rnd() < 0.1) edificios.push([jx, jy, 9 + rnd() * 3, 9 + rnd() * 3, 2 + Math.floor(rnd() * 3), 0]);
        else parque.push([jx, jy]);
        continue;
      }
      if (d < muro + 15) {                          // bulevar junto a la pista: palmeras
        if (rnd() < 0.35) palmeras.push([jx, jy]);
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
  pbr(matParque, "leafy_grass", { repetir: [1, 1] });
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
  for (const [x, y, lx, ly, pisos, base] of edificios) {
    const M = mallaDe(x, y, rnd() < 0.55 ? 0 : 1);
    const h = pisos * PISO, col = color.setHex(paleta[Math.floor(rnd() * paleta.length)]).clone();
    const esq = [[x - lx / 2, y - ly / 2], [x + lx / 2, y - ly / 2], [x + lx / 2, y + ly / 2], [x - lx / 2, y + ly / 2]];
    for (let i = 0; i < 4; i++) {
      const [ax, ay] = esq[i], [bx, by] = esq[(i + 1) % 4];
      const largo = Math.hypot(bx - ax, by - ay), fuera = P((ax + bx) / 2 - x, (ay + by) / 2 - y, 0);
      const vanos = Math.max(1, Math.round(largo / VANO));
      M.quad(P(ax, ay, base), P(bx, by, base), P(bx, by, base + h), P(ax, ay, base + h),
        [[0, 0], [vanos, 0], [vanos, pisos], [0, pisos]], col, fuera);
      // Cornisa saliente
      const o = 0.35, cx0 = ax + Math.sign(ax - x) * o, cy0 = ay + Math.sign(ay - y) * o, cx1 = bx + Math.sign(bx - x) * o, cy1 = by + Math.sign(by - y) * o;
      const oscuro = col.clone().multiplyScalar(0.88);
      M.quad(P(cx0, cy0, base + h), P(cx1, cy1, base + h), P(cx1, cy1, base + h + 0.55), P(cx0, cy0, base + h + 0.55), lisoUV, oscuro, fuera);
    }
    const o = 0.35;
    const ti = esq.map(([ex, ey]) => P(ex + Math.sign(ex - x) * o, ey + Math.sign(ey - y) * o, base + h + 0.55));
    if (rnd() < 0.45) {                             // techo de teja a cuatro aguas
      const cima = P(x, y, base + h + 0.55 + Math.min(lx, ly) * 0.32);
      for (let i = 0; i < 4; i++) {
        const a = ti[i], b = ti[(i + 1) % 4];
        const fuera = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5).sub(cima).setY(0.5);
        techosTeja.tri(a, b, cima, [[a.x / 3, a.z / 3], [b.x / 3, b.z / 3], [cima.x / 3, cima.z / 3]], new THREE.Color(1, 1, 1), fuera);
      }
    } else {
      M.quad(ti[0], ti[1], ti[2], ti[3], lisoUV, col.clone().multiplyScalar(0.8), ARRIBA);
    }
  }
  const matFachadas = [texturaFachada("#47704f"), texturaFachada("#3f5f86")].map((map) =>
    new THREE.MeshStandardMaterial({ map, vertexColors: true, roughness: 0.85 }));
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

  // Pino piñonero: tronco + copa ancha y aplanada (tres masas irregulares)
  const copaPino = (() => {
    const partes = [];
    for (const [dx, dy, dz, r] of [[0, 0, 0, 3.2], [1.8, -0.3, 0.8, 2.4], [-1.6, -0.2, -0.9, 2.5], [0.3, 0.4, -1.8, 2.2]]) {
      const g = new THREE.IcosahedronGeometry(r, 1);
      const p = g.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const v = new THREE.Vector3().fromBufferAttribute(p, i);
        const k = 1 + 0.22 * (fbm(v.x * 0.9 + dx, v.z * 0.9 + dz, 3) - 0.5);
        p.setXYZ(i, v.x * k + dx, v.y * 0.42 * k + dy, v.z * k + dz);
      }
      partes.push(g);
    }
    const g = mergeGeometries(partes);
    g.computeVertexNormals();
    return g;
  })();
  const troncoPino = new THREE.CylinderGeometry(0.22, 0.35, 6, 7);
  troncoPino.translate(0, 3, 0);
  const matFollaje = new THREE.MeshStandardMaterial({ map: texturaFollaje(), roughness: 0.9 });
  const iTroncoN = new THREE.InstancedMesh(troncoPino, matCorteza, pinos.length);
  const iCopa = new THREE.InstancedMesh(copaPino, matFollaje, pinos.length);
  pinos.forEach(([x, y, h, esc], i) => {
    q.setFromAxisAngle(ARRIBA, rnd() * Math.PI * 2);
    m.compose(P(x, y, h), q, e.set(esc, esc, esc)); iTroncoN.setMatrixAt(i, m);
    m.compose(P(x, y, h + 6.3 * esc), q, e.set(esc, esc, esc)); iCopa.setMatrixAt(i, m);
    iCopa.setColorAt(i, color.setHSL(0.24 + rnd() * 0.06, 0.25 + rnd() * 0.15, 0.62 + rnd() * 0.25));
  });
  iTroncoN.castShadow = iCopa.castShadow = true;
  agregar("arboles", iTroncoN, iCopa);

  // ---------------------------------------------------------------- público en graderías
  const personas = [], banderas = [], gradas = new Malla();
  const tramos = [[0, 140], [150, 215], [380, 440], [520, 600], [880, 960], [1000, pista.largo]];
  const enTramo = (s) => tramos.some(([a, b]) => s >= a && s <= b);
  const gris = new THREE.Color(0x9aa1a9);
  for (let k = 0; k < pista.centro.length - 2; k += 2) {
    const [s, x, y, h] = pista.centro[k], [, x2, y2, h2] = pista.centro[k + 2];
    if (!enTramo(s)) continue;
    for (const lado of [1, -1]) {
      const libre = (off) => {
        const px = x - Math.sin(h) * off, py = y + Math.cos(h) * off;
        const [, sd] = dist(px, py);
        return py > ORILLA + 1 && !(Math.abs(sd - s) > 30 && Math.abs(sd - s) < pista.largo - 30);
      };
      if (!libre(lado * (muro + 4))) continue;
      // Escalones de la gradería (3 filas)
      for (let fila = 0; fila < 3; fila++) {
        const o0 = lado * (muro + 0.9 + fila * 0.9), o1 = lado * (muro + 1.8 + fila * 0.9), alto = 0.35 * (fila + 1);
        const pt = (xx, yy, hh, off, z) => P(xx - Math.sin(hh) * off, yy + Math.cos(hh) * off, z);
        gradas.quad(pt(x, y, h, o0, alto), pt(x2, y2, h2, o0, alto), pt(x2, y2, h2, o1, alto), pt(x, y, h, o1, alto), [[0, 0], [1, 0], [1, 1], [0, 1]], gris, ARRIBA);
        const frente = new THREE.Vector3(Math.sin(h) * lado, 0, Math.cos(h) * lado);   // hacia la pista
        gradas.quad(pt(x, y, h, o0, alto - 0.35), pt(x2, y2, h2, o0, alto - 0.35), pt(x2, y2, h2, o0, alto), pt(x, y, h, o0, alto), [[0, 0], [1, 0], [1, 1], [0, 1]], gris.clone().multiplyScalar(0.85), frente);
        if (rnd() > 0.82) continue;                  // una persona por metro y fila (antes dos)
        {
          const t = 0.2 + rnd() * 0.6, off = lado * (muro + 1.35 + fila * 0.9);
          const px = x + (x2 - x) * t - Math.sin(h) * off, py = y + (y2 - y) * t + Math.cos(h) * off;
          const tramo = tramos.findIndex(([a, b]) => s >= a && s <= b);
          personas.push([px, py, alto, h + (lado > 0 ? Math.PI / 2 : -Math.PI / 2), rnd() < 0.3, tramo]);
          if (fila === 2 && rnd() < 0.05) banderas.push([px, py, h, alto]);
        }
      }
    }
  }
  const matGrada = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9 });
  pbr(matGrada, "grey_plaster", { repetir: [1, 1], rugosidad: false });
  const grada = new THREE.Mesh(gradas.geometria(), matGrada);
  grada.receiveShadow = true;
  agregar("publico", grada);

  // Persona: piernas, torso y brazos (abajo o arriba saludando) + cabeza aparte
  const cuerpoPersona = (brazosArriba) => {
    const partes = [];
    const pieza = (g, x, y, z, rz = 0, col = 0xffffff) => {
      g.rotateZ(rz); g.translate(x, y, z);
      const c = new THREE.Color(col), arr = [];
      for (let i = 0; i < g.attributes.position.count; i++) arr.push(c.r, c.g, c.b);
      g.setAttribute("color", new THREE.Float32BufferAttribute(arr, 3));
      g.deleteAttribute("uv");
      partes.push(g);   // indexada: cada vértice una sola vez
    };
    const pierna = () => new THREE.CapsuleGeometry(0.075, 0.62, 2, 5);
    pieza(pierna(), 0, 0.4, 0.09, 0, 0x2b3445); pieza(pierna(), 0, 0.4, -0.09, 0, 0x2b3445);
    pieza(new THREE.CapsuleGeometry(0.17, 0.45, 3, 7), 0, 1.08, 0);
    const brazo = () => new THREE.CapsuleGeometry(0.055, 0.5, 2, 5);
    if (brazosArriba) { pieza(brazo(), 0, 1.6, 0.27, 0.35); pieza(brazo(), 0, 1.6, -0.27, -0.35); }
    else { pieza(brazo(), 0, 1.02, 0.24, 0.12); pieza(brazo(), 0, 1.02, -0.24, -0.12); }
    return mergeGeometries(partes);
  };
  const ropa = [0xe11d48, 0x2563eb, 0xfacc15, 0xf8fafc, 0x16a34a, 0xf97316, 0x111827, 0x7c3aed, 0x0ea5e9, 0xdc2626];
  const piel = [0xf1c27d, 0xe0ac69, 0xc68642, 0x8d5524, 0xffdbac];
  const matPersona = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 });
  const tiempoGPU = { value: 0 };
  // Salto de la gente que saluda, calculado en el shader con el número de cada instancia
  const saltar = (mat) => {
    mat.onBeforeCompile = (sh) => {
      sh.uniforms.uTiempo = tiempoGPU;
      sh.vertexShader = "uniform float uTiempo;\n" + sh.vertexShader.replace("#include <begin_vertex>",
        "#include <begin_vertex>\n  transformed.y += max(0.0, sin(uTiempo * 7.0 + float(gl_InstanceID) * 1.7)) * 0.12;");
    };
    return mat;
  };
  // Un grupo por tramo de pista y por postura: la tarjeta gráfica solo dibuja las graderías en cámara
  const cuerpos = [cuerpoPersona(false), cuerpoPersona(true)];
  const geoCabeza = new THREE.SphereGeometry(0.12, 8, 6);
  const matSaltar = saltar(matPersona.clone()), matCabeza = new THREE.MeshStandardMaterial({ roughness: 0.7 });
  const matCabezaSaltar = saltar(new THREE.MeshStandardMaterial({ roughness: 0.7 }));
  const combinaciones = [];
  for (let tr = 0; tr < tramos.length; tr++) for (const arriba of [false, true]) combinaciones.push([tr, arriba]);
  const grupos = combinaciones.map(([tr, arriba]) => {
    const lista = personas.filter((p) => p[4] === arriba && p[5] === tr);
    if (!lista.length) return null;
    const im = new THREE.InstancedMesh(cuerpos[+arriba], arriba ? matSaltar : matPersona, lista.length);
    const cab = new THREE.InstancedMesh(geoCabeza, arriba ? matCabezaSaltar : matCabeza, lista.length);
    lista.forEach(([x, y, z, rot], i) => {
      q.setFromAxisAngle(ARRIBA, rot);
      m.compose(P(x, y, z), q, e.set(1, 0.9 + rnd() * 0.2, 1)); im.setMatrixAt(i, m);
      im.setColorAt(i, color.setHex(ropa[Math.floor(rnd() * ropa.length)]));
      m.compose(P(x, y, z + 1.55), q, e.set(1, 1, 1)); cab.setMatrixAt(i, m);
      cab.setColorAt(i, color.setHex(piel[Math.floor(rnd() * piel.length)]));
    });
    im.computeBoundingSphere(); cab.computeBoundingSphere();   // para descartar lo que no se ve
    agregar("publico", im, cab);
    return { im, cab };
  });
  void grupos;

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
    if (d < muro + 3 || py < ORILLA + 1 || (Math.abs(sd - s) > 30 && Math.abs(sd - s) < pista.largo - 30)) continue;
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
    renderer.toneMappingExposure = mojado ? 0.55 : 0.7;
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
