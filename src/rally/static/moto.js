// Moto de velocidad tipo MotoGP con su piloto, hecha con geometría de three.js (sin modelos
// descargados). Diseño propio con los colores del proyecto, los mismos del carro: azul, azul
// oscuro, dorado, amarillo y blanco, con el número 24. Detalle de prototipo de carreras: carenado
// con cortes angulares, fibra de carbono, alerones dobles, cúpula ahumada, escape de titanio con
// el tornasol del calor, horquilla dorada, discos perforados con pinzas radiales, basculante de
// aluminio, cadena y amortiguador con resorte amarillo.
// Las medidas son las del simulador (rally/moto.py): largo 2.1 m, ancho 0.8 m con el piloto,
// 1.45 m entre ejes. El origen está en el suelo, en medio de los dos ejes: el visor inclina el
// grupo entero sobre la línea de contacto de las llantas. x hacia adelante, y arriba, z al costado.

import * as THREE from "three";
import { toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";

const R_LLANTA = 0.31;
const AZUL = "#1a3fb8", AZUL_OSCURO = "#0b1d5c", DORADO = "#b8862b", AMARILLO = "#ffd23f", BLANCO = "#f8fafc";

// ------------------------------------------------------------------ texturas pintadas en canvas
function lienzo(w, h) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  return [c, c.getContext("2d")];
}
function aTextura(c, { repetir = null, srgb = true } = {}) {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repetir) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repetir); }
  return t;
}

// Fibra de carbono: tejido sarga 2x2, cada hilo con su brillo
function patronCarbono(g, x0, y0, w, h, celda = 16) {
  for (let y = 0; y < h; y += celda) {
    for (let x = 0; x < w; x += celda) {
      const k = ((x / celda) + (y / celda)) % 4 < 2;
      const gr = k ? g.createLinearGradient(x0 + x, 0, x0 + x + celda, 0) : g.createLinearGradient(0, y0 + y, 0, y0 + y + celda);
      gr.addColorStop(0, "#0d0f13"); gr.addColorStop(0.5, k ? "#2a2e36" : "#1c1f25"); gr.addColorStop(1, "#0d0f13");
      g.fillStyle = gr;
      g.fillRect(x0 + x, y0 + y, celda, celda);
    }
  }
}
function texturaCarbono() {
  const [c, g] = lienzo(256, 256);
  patronCarbono(g, 0, 0, 256, 256, 16);
  return aTextura(c, { repetir: [6, 6] });
}

// Decoración del carenado. El lienzo tiene dos mitades: arriba el costado derecho (+z) y abajo el
// izquierdo (-z), dibujado en espejo para que el frente quede adelante en los dos lados y los
// textos se lean bien. En cada mitad, a la derecha está la nariz de la moto.
// Rango que cubre la decoración del carenado (x de la cola a la nariz, y del piso de la pieza al techo)
const LADOS_CARENADO = [-0.06, 1.07, 0.26, 0.94];
function dibujarCostado(g, oy, W, H, espejo) {
  const [x0, x1, y0, y1] = LADOS_CARENADO;
  // Cada punto se da en metros sobre la moto y se convierte a píxeles del lienzo
  const M = (x, y) => { const px = ((x - x0) / (x1 - x0)) * W; return [espejo ? W - px : px, oy + (1 - (y - y0) / (y1 - y0)) * H]; };
  const poli = (pts, color) => {
    g.fillStyle = color;
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(...M(x, y)) : g.moveTo(...M(x, y))));
    g.closePath();
    g.fill();
  };
  // Base: azul arriba que oscurece hacia abajo
  const base = g.createLinearGradient(0, oy, 0, oy + H);
  base.addColorStop(0, "#2148c9"); base.addColorStop(0.5, AZUL); base.addColorStop(1, AZUL_OSCURO);
  g.fillStyle = base; g.fillRect(0, oy, W, H);
  // Parte baja del costado en fibra de carbono, con un corte diagonal
  g.save();
  g.beginPath();
  [[-0.1, 0.43], [0.2, 0.38], [0.45, 0.33], [0.45, 0.2], [-0.1, 0.2]].forEach(([x, y], i) =>
    (i ? g.lineTo(...M(x, y)) : g.moveTo(...M(x, y))));
  g.closePath();
  g.clip();
  patronCarbono(g, 0, oy, W, H, 22);
  g.restore();
  // Cortes blancos angulares que corren hacia la nariz (como astillas)
  poli([[0.14, 0.7], [0.42, 0.82], [0.62, 0.86], [0.28, 0.68]], BLANCO);
  poli([[0.5, 0.74], [0.97, 0.73], [1.02, 0.68], [0.6, 0.68]], BLANCO);
  poli([[-0.04, 0.47], [0.2, 0.45], [0.06, 0.41]], BLANCO);
  // Franjas dorada y amarilla en diagonal (la firma del carro)
  poli([[-0.1, 0.4], [1.1, 0.86], [1.1, 0.885], [-0.1, 0.43]], DORADO);
  poli([[-0.1, 0.437], [1.1, 0.893], [1.1, 0.9], [-0.1, 0.445]], AMARILLO);
  // Tomas de aire pintadas detrás de la rueda: ranuras oscuras con borde claro
  for (let k = 0; k < 3; k++) {
    const x = 0.27 + k * 0.035, y = 0.66 - k * 0.07;
    poli([[x, y], [x + 0.03, y], [x - 0.05, y - 0.13], [x - 0.08, y - 0.13]], "#05070c");
    poli([[x + 0.03, y], [x + 0.036, y], [x - 0.044, y - 0.13], [x - 0.05, y - 0.13]], "rgba(248,250,252,.55)");
  }
  // Chevrones /// en amarillo, atrás del costado
  for (let k = 0; k < 3; k++) {
    const x = -0.02 + k * 0.03;
    poli([[x, 0.56], [x + 0.016, 0.56], [x - 0.012, 0.49], [x - 0.028, 0.49]], AMARILLO);
  }
  g.save();
  g.textAlign = "center"; g.textBaseline = "middle";
  // El 24 del carro en la nariz, blanco con borde dorado
  g.font = "italic 900 230px Inter, Arial";
  g.lineWidth = 16; g.strokeStyle = DORADO;
  g.strokeText("24", ...M(0.8, 0.79));
  g.fillStyle = BLANCO; g.fillText("24", ...M(0.8, 0.79));
  // Nombre del equipo en el costado
  g.font = "italic 900 78px Inter, Arial";
  g.fillStyle = AMARILLO; g.fillText("AUTONOMOUS", ...M(0.15, 0.61));
  g.font = "italic 900 64px Inter, Arial";
  g.fillStyle = BLANCO; g.fillText("RALLY · GP", ...M(0.17, 0.555));
  // Calcomanías técnicas (las herramientas del proyecto) sobre el carbono
  g.font = "700 34px Inter, Arial";
  [["MLOps", 0.02, 0.36], ["PPO", 0.13, 0.335], ["DVC", 0.22, 0.31]].forEach(([t, x, y]) => {
    const w = g.measureText(t).width + 22, [px, py] = M(x, y);
    g.fillStyle = "rgba(248,250,252,.92)"; g.fillRect(px - w / 2, py - 24, w, 44);
    g.fillStyle = AZUL_OSCURO; g.fillText(t, px, py - 1);
  });
  g.restore();
  // Desgaste de carrera: puntitos y rayones finos
  g.globalAlpha = 0.08;
  g.fillStyle = "#000";
  for (let k = 0; k < 900; k++) g.fillRect(Math.random() * W, oy + Math.random() * H, 2, 2);
  g.globalAlpha = 1;
}
function texturaCarenado() {
  const W = 2048, H = 768;
  const [c, g] = lienzo(W, H * 2);
  dibujarCostado(g, 0, W, H, false);
  dibujarCostado(g, H, W, H, true);
  return aTextura(c);
}

// Colín: número grande, chevrones y franja; mismas dos mitades en espejo
function texturaColin() {
  const W = 1024, H = 384;
  const [c, g] = lienzo(W, H * 2);
  for (const [oy, espejo] of [[0, false], [H, true]]) {
    const X = (x) => (espejo ? W - x : x);
    const base = g.createLinearGradient(0, oy, 0, oy + H);
    base.addColorStop(0, AZUL); base.addColorStop(1, AZUL_OSCURO);
    g.fillStyle = base; g.fillRect(0, oy, W, H);
    g.fillStyle = BLANCO;
    g.beginPath(); g.moveTo(X(80), oy + 330); g.lineTo(X(980), oy + 140); g.lineTo(X(1000), oy + 210); g.lineTo(X(140), oy + 380); g.closePath(); g.fill();
    g.fillStyle = AMARILLO;
    g.beginPath(); g.moveTo(X(60), oy + 300); g.lineTo(X(1000), oy + 110); g.lineTo(X(1010), oy + 126); g.lineTo(X(70), oy + 318); g.closePath(); g.fill();
    for (let k = 0; k < 3; k++) {
      const x = 260 + k * 46;
      g.beginPath(); g.moveTo(X(x), oy + 70); g.lineTo(X(x + 24), oy + 70); g.lineTo(X(x - 8), oy + 190); g.lineTo(X(x - 32), oy + 190); g.closePath(); g.fill();
    }
    g.font = "italic 900 170px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
    g.lineWidth = 12; g.strokeStyle = DORADO; g.strokeText("24", X(640), oy + 150);
    g.fillStyle = BLANCO; g.fillText("24", X(640), oy + 150);
  }
  return aTextura(c);
}

// Escape de titanio: plateado que se tiñe de paja, morado y azul donde pega el calor
function texturaTitanio() {
  const [c, g] = lienzo(512, 32);
  const gr = g.createLinearGradient(0, 0, 512, 0);
  gr.addColorStop(0, "#7d6bb5"); gr.addColorStop(0.12, "#4a5fb8"); gr.addColorStop(0.28, "#c7a25a");
  gr.addColorStop(0.45, "#d8dbe0"); gr.addColorStop(1, "#c4c8cf");
  g.fillStyle = gr; g.fillRect(0, 0, 512, 32);
  g.globalAlpha = 0.18;
  for (let y = 0; y < 32; y += 2) { g.fillStyle = y % 4 ? "#ffffff" : "#000000"; g.fillRect(0, y, 512, 1); }
  return aTextura(c);
}

// Disco de freno perforado: anillo de acero con agujeros (la transparencia los recorta)
function texturaDisco() {
  const [c, g] = lienzo(256, 256);
  g.clearRect(0, 0, 256, 256);
  g.fillStyle = "#c9ced6"; g.beginPath(); g.arc(128, 128, 128, 0, Math.PI * 2); g.fill();
  g.strokeStyle = "rgba(90,96,110,.5)"; g.lineWidth = 1;
  for (let r = 70; r < 128; r += 6) { g.beginPath(); g.arc(128, 128, r, 0, Math.PI * 2); g.stroke(); }
  g.globalCompositeOperation = "destination-out";
  for (let anillo = 0; anillo < 3; anillo++) {
    const r = 82 + anillo * 14, n = 24;
    for (let k = 0; k < n; k++) {
      const a = (k / n) * Math.PI * 2 + anillo * 0.09;
      g.beginPath(); g.arc(128 + Math.cos(a) * r, 128 + Math.sin(a) * r, 3.4, 0, Math.PI * 2); g.fill();
    }
  }
  g.globalCompositeOperation = "source-over";
  return aTextura(c);
}

// Letras del costado de la llanta, en círculo (el anillo usa coordenadas planas: centro del lienzo = eje)
function texturaFlanco(rTexto) {
  const [c, g] = lienzo(1024, 1024);
  g.clearRect(0, 0, 1024, 1024);
  const texto = " AUTONOMOUS RALLY  ·  SLICK  ·  24  ·  AUTONOMOUS RALLY  ·  SLICK  ·  24  ·";
  g.font = "italic 900 34px Inter, Arial";
  g.textAlign = "center"; g.textBaseline = "middle";
  const paso = (Math.PI * 2) / texto.length;
  for (let k = 0; k < texto.length; k++) {
    const a = -Math.PI / 2 + k * paso;
    g.save();
    g.translate(512 + Math.cos(a) * rTexto, 512 + Math.sin(a) * rTexto);
    g.rotate(a + Math.PI / 2);
    g.fillStyle = /[0-9]/.test(texto[k]) ? BLANCO : AMARILLO;
    g.fillText(texto[k], 0, 0);
    g.restore();
  }
  return aTextura(c);
}

// Casco: blanco con banda azul, franja amarilla de frente a nuca y el 24 a los lados
function texturaCasco() {
  const [c, g] = lienzo(1024, 512);
  g.fillStyle = BLANCO; g.fillRect(0, 0, 1024, 512);
  g.fillStyle = AZUL; g.fillRect(0, 250, 1024, 120);
  g.fillStyle = AZUL_OSCURO; g.fillRect(0, 370, 1024, 142);
  g.fillStyle = AMARILLO; g.fillRect(0, 238, 1024, 14);
  // Franja central de frente (u = 0.5) a nuca (u = 0 y 1), por encima
  g.fillStyle = AMARILLO; g.fillRect(480, 0, 64, 250); g.fillRect(0, 0, 32, 250); g.fillRect(992, 0, 32, 250);
  g.fillStyle = AZUL; g.fillRect(500, 0, 24, 250);
  g.font = "italic 900 110px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
  for (const u of [256, 768]) {
    g.lineWidth = 8; g.strokeStyle = AZUL_OSCURO; g.strokeText("24", u, 170);
    g.fillStyle = DORADO; g.fillText("24", u, 170);
  }
  return aTextura(c);
}

// ------------------------------------------------------------------ geometría
// Pieza extruida a lo ancho a partir de un perfil lateral, redondeada (bisel con normales suaves),
// opcionalmente afinada hacia la nariz o el colín, y con la decoración proyectada en los costados.
function pieza(perfil, ancho, mat, { bisel = 0.03, afinar = null, lados = null } = {}) {
  const s = new THREE.Shape();
  s.moveTo(perfil[0][0], perfil[0][1]);
  for (const [x, y] of perfil.slice(1)) s.lineTo(x, y);
  s.closePath();
  const prof = Math.max(ancho - 2 * bisel, 0.004);
  let geo = new THREE.ExtrudeGeometry(s, { depth: prof, bevelEnabled: true, bevelThickness: bisel,
    bevelSize: bisel * 0.85, bevelSegments: 5, curveSegments: 16 });
  geo.translate(0, 0, -prof / 2);
  if (afinar) {
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) p.setZ(i, p.getZ(i) * afinar(p.getX(i), p.getY(i)));
  }
  geo.deleteAttribute("normal");
  geo = toCreasedNormals(geo, Math.PI / 3.2);
  if (lados) proyectarLados(geo, lados);
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

// UV de costado: u a lo largo (cola → nariz), v a lo alto; el lado -z usa la mitad de abajo en espejo
function proyectarLados(geo, [x0, x1, y0, y1]) {
  const p = geo.attributes.position, n = geo.attributes.normal;
  const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const u = THREE.MathUtils.clamp((p.getX(i) - x0) / (x1 - x0), 0, 1);
    const v = THREE.MathUtils.clamp((p.getY(i) - y0) / (y1 - y0), 0, 1);
    const izquierdo = n.getZ(i) < 0;
    uv[2 * i] = izquierdo ? 1 - u : u;
    uv[2 * i + 1] = izquierdo ? 0.5 * v : 0.5 + 0.5 * v;
  }
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
}

// Afinado suave: 1 en el centro, `punta` en los extremos
const suave = (t) => t * t * (3 - 2 * t);
function afinado({ xNariz = null, puntaNariz = 0.6, xCola = null, puntaCola = 0.7, xMax = 1.1, xMin = -1.1 }) {
  return (x) => {
    let f = 1;
    if (xNariz !== null && x > xNariz) f *= 1 - (1 - puntaNariz) * suave(THREE.MathUtils.clamp((x - xNariz) / (xMax - xNariz), 0, 1));
    if (xCola !== null && x < xCola) f *= 1 - (1 - puntaCola) * suave(THREE.MathUtils.clamp((xCola - x) / (xCola - xMin), 0, 1));
    return f;
  };
}

function malla(geo, mat, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  return m;
}

// Tubo a lo largo de una curva (escape, cadena, cables)
function tubo(puntos, radio, mat, cerrado = false, segmentos = 64) {
  const curva = new THREE.CatmullRomCurve3(puntos.map(([x, y, z]) => new THREE.Vector3(x, y, z)), cerrado, "catmullrom", 0.2);
  return malla(new THREE.TubeGeometry(curva, segmentos, radio, 12, cerrado), mat);
}

// Cilindro entre dos puntos
function barra(a, b, radio, mat, radio2 = radio) {
  const va = new THREE.Vector3(...a), vb = new THREE.Vector3(...b);
  const largo = va.distanceTo(vb);
  const m = malla(new THREE.CylinderGeometry(radio2, radio, largo, 16), mat);
  m.position.copy(va).add(vb).multiplyScalar(0.5);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), vb.clone().sub(va).normalize());
  return m;
}

// Llanta slick redondeada (perfil de revolución) con rin negro de cinco rayos partidos y filete amarillo
function crearRueda(ancho, mats) {
  const giro = new THREE.Group();
  const h = 0.078, rc = R_LLANTA - h, rRin = rc - 0.02;
  const perfil = [new THREE.Vector2(rRin, -ancho * 0.42)];
  for (let k = 0; k <= 24; k++) {
    const a = -Math.PI / 2 + (Math.PI * k) / 24;
    perfil.push(new THREE.Vector2(rc + h * Math.cos(a), (ancho / 2) * Math.sin(a)));
  }
  perfil.push(new THREE.Vector2(rRin, ancho * 0.42));
  const llanta = new THREE.LatheGeometry(perfil, 56);
  llanta.rotateX(Math.PI / 2);
  giro.add(malla(llanta, mats.goma));
  // Rin: aro, filete amarillo a ambos lados, cubo y cinco rayos en Y
  const aro = new THREE.LatheGeometry([new THREE.Vector2(rRin - 0.016, -ancho * 0.4), new THREE.Vector2(rRin, -ancho * 0.4),
    new THREE.Vector2(rRin, ancho * 0.4), new THREE.Vector2(rRin - 0.016, ancho * 0.4)], 48);
  aro.rotateX(Math.PI / 2);
  giro.add(malla(aro, mats.rin));
  for (const lado of [1, -1]) {
    const filete = malla(new THREE.RingGeometry(rRin - 0.012, rRin - 0.003, 56), mats.filete, 0, 0, lado * (ancho * 0.4 + 0.002));
    if (lado < 0) filete.rotation.y = Math.PI;
    giro.add(filete);
  }
  // Letras en los dos flancos de la llanta
  const rFuera = R_LLANTA - 0.035;
  for (const lado of [1, -1]) {
    const flanco = malla(new THREE.RingGeometry(rRin + 0.012, rFuera, 64), mats.flanco, 0, 0, lado * (ancho / 2 + 0.003));
    if (lado < 0) flanco.rotation.y = Math.PI;
    flanco.castShadow = false;
    giro.add(flanco);
  }
  const cubo = malla(new THREE.CylinderGeometry(0.045, 0.045, ancho * 0.85, 20), mats.rin);
  cubo.rotation.x = Math.PI / 2;
  giro.add(cubo);
  const largoRayo = rRin - 0.05;
  for (let k = 0; k < 5; k++) {
    for (const abre of [-0.11, 0.11]) {
      const brazo = new THREE.Group();
      brazo.rotation.z = (k * 2 * Math.PI) / 5 + abre;
      const rayo = malla(new THREE.BoxGeometry(0.016, largoRayo, 0.026), mats.rin, 0, 0.04 + largoRayo / 2, 0);
      brazo.add(rayo);
      giro.add(brazo);
    }
  }
  return giro;
}

// Disco perforado flotante: pista de frenado con agujeros, portadiscos dorado y botones
function crearDisco(radio, mats) {
  const g = new THREE.Group();
  const pista = new THREE.Mesh(new THREE.RingGeometry(radio * 0.62, radio, 72), mats.disco);
  g.add(pista);
  const porta = new THREE.Mesh(new THREE.RingGeometry(0.05, radio * 0.64, 40), mats.dorado);
  porta.position.z = 0.001;
  g.add(porta);
  for (let k = 0; k < 10; k++) {
    const a = (k / 10) * Math.PI * 2;
    const b = malla(new THREE.CylinderGeometry(0.008, 0.008, 0.014, 10), mats.dorado,
      Math.cos(a) * radio * 0.63, Math.sin(a) * radio * 0.63, 0);
    b.rotation.x = Math.PI / 2;
    g.add(b);
  }
  return g;
}

// Pinza radial de cuatro pistones (no gira con la rueda)
function crearPinza(mats) {
  const p = new THREE.Group();
  p.add(malla(new THREE.BoxGeometry(0.11, 0.045, 0.05), mats.pinza));
  p.add(malla(new THREE.BoxGeometry(0.09, 0.012, 0.052), mats.negro, 0, 0.026, 0));
  for (const x of [-0.03, 0.03]) {
    const t = malla(new THREE.CylinderGeometry(0.009, 0.009, 0.056, 10), mats.metal, x, 0.02, 0);
    t.rotation.x = Math.PI / 2;
    p.add(t);
  }
  return p;
}

// Corona de la transmisión con dientes
function crearCorona(radio, dientes, mat) {
  const s = new THREE.Shape();
  for (let k = 0; k < dientes * 2; k++) {
    const a = (k / (dientes * 2)) * Math.PI * 2, r = k % 2 ? radio : radio * 0.92;
    k ? s.lineTo(Math.cos(a) * r, Math.sin(a) * r) : s.moveTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  s.holes.push(new THREE.Path().absarc(0, 0, radio * 0.45, 0, Math.PI * 2, true));
  const geo = new THREE.ExtrudeGeometry(s, { depth: 0.006, bevelEnabled: false });
  geo.translate(0, 0, -0.003);
  return malla(geo, mat);
}

// ------------------------------------------------------------------ piloto
function crearPiloto(mats) {
  // El piloto agachado (posición de carrera). Su grupo se desplaza hacia el interior de la curva.
  const p = new THREE.Group();
  const add = (geo, mat, x, y, z, rx = 0, ry = 0, rz = 0) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.castShadow = true; p.add(m); return m;
  };
  // Torso tendido sobre el tanque, franja blanca en el pecho, joroba aerodinámica dorada, hombreras blancas
  add(new THREE.CapsuleGeometry(0.155, 0.4, 8, 16), mats.traje, -0.12, 0.98, 0, 0, 0, -1.2).scale.set(1, 1, 0.92);
  add(new THREE.CapsuleGeometry(0.157, 0.06, 6, 16), mats.trajeBlanco, 0.04, 1.02, 0, 0, 0, -1.2).scale.set(1, 1, 0.92);
  add(new THREE.SphereGeometry(0.13, 18, 12), mats.joroba, -0.32, 1.07, 0).scale.set(1.3, 0.75, 0.8);
  for (const z of [0.14, -0.14]) add(new THREE.SphereGeometry(0.07, 14, 10), mats.trajeBlanco, 0.1, 1.04, z);
  // Casco con su decoración, visera tornasolada y alerón trasero
  const casco = add(new THREE.SphereGeometry(0.15, 32, 24), mats.casco, 0.21, 1.16, 0);
  casco.rotation.y = 0;
  add(new THREE.SphereGeometry(0.153, 28, 18, -0.95, 1.9, 1.05, 0.72), mats.visera, 0.215, 1.16, 0, 0, Math.PI / 2, 0);
  add(new THREE.BoxGeometry(0.1, 0.02, 0.12), mats.trajeAzul, 0.08, 1.27, 0, 0, 0, 0.25);
  // Brazos al manubrio (antebrazo azul oscuro), guantes negros con nudillera
  for (const z of [0.17, -0.17]) {
    add(new THREE.CapsuleGeometry(0.05, 0.2, 4, 10), mats.traje, 0.13, 0.98, z, 0, 0, -1.1);
    add(new THREE.CapsuleGeometry(0.044, 0.17, 4, 10), mats.trajeAzul, 0.3, 0.89, z * 1.05, 0, 0, -0.45);
    add(new THREE.SphereGeometry(0.045, 12, 10), mats.guante, 0.39, 0.82, z * 1.08).scale.set(1.2, 0.9, 1);
    // Piernas dobladas sobre los estribos, deslizador amarillo en la rodilla, botas blancas de carreras
    add(new THREE.CapsuleGeometry(0.07, 0.33, 4, 10), mats.traje, -0.17, 0.71, z * 1.18, 0, 0, 0.75);
    add(new THREE.CapsuleGeometry(0.058, 0.28, 4, 10), mats.trajeAzul, -0.2, 0.49, z * 1.3, 0, 0, -0.5);
    add(new THREE.CylinderGeometry(0.042, 0.042, 0.025, 16), mats.deslizador, -0.04, 0.61, z * 1.42, Math.PI / 2, 0, 0);
    add(new THREE.BoxGeometry(0.2, 0.075, 0.08), mats.bota, -0.12, 0.35, z * 1.3);
    add(new THREE.BoxGeometry(0.06, 0.12, 0.085), mats.bota, -0.2, 0.41, z * 1.3, 0, 0, -0.4);
  }
  return p;
}

// ------------------------------------------------------------------ moto
// Devuelve el grupo, las ruedas (mismo formato que el carro: pivote → giro) y las luces.
export function crearMoto({ largo: L = 2.1, ejes = 1.45 } = {}) {
  const grupo = new THREE.Group();
  const carbonoTex = texturaCarbono();
  const mats = {
    pintura: new THREE.MeshPhysicalMaterial({ map: texturaCarenado(), metalness: 0.35, roughness: 0.28,
      clearcoat: 1, clearcoatRoughness: 0.04 }),
    colin: new THREE.MeshPhysicalMaterial({ map: texturaColin(), metalness: 0.35, roughness: 0.28, clearcoat: 1,
      clearcoatRoughness: 0.04 }),
    azul: new THREE.MeshPhysicalMaterial({ color: 0x1a3fb8, metalness: 0.4, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.04 }),
    carbono: new THREE.MeshPhysicalMaterial({ map: carbonoTex, metalness: 0.3, roughness: 0.38, clearcoat: 1,
      clearcoatRoughness: 0.08, side: THREE.DoubleSide }),
    negro: new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 0.5, metalness: 0.3 }),
    gamuza: new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 0.95 }),
    dorado: new THREE.MeshStandardMaterial({ color: 0xc9a227, metalness: 1, roughness: 0.22 }),
    filete: new THREE.MeshStandardMaterial({ color: 0xffd23f, metalness: 0.2, roughness: 0.35, side: THREE.DoubleSide }),
    metal: new THREE.MeshStandardMaterial({ color: 0xbfc4cc, metalness: 0.95, roughness: 0.3 }),
    aluminio: new THREE.MeshStandardMaterial({ color: 0x9aa1ab, metalness: 0.9, roughness: 0.4 }),
    titanio: new THREE.MeshStandardMaterial({ map: texturaTitanio(), metalness: 0.95, roughness: 0.28 }),
    titanioLiso: new THREE.MeshStandardMaterial({ color: 0xb9bdc8, metalness: 0.95, roughness: 0.3 }),
    goma: new THREE.MeshStandardMaterial({ color: 0x121212, roughness: 0.82, metalness: 0.0 }),
    // Radio del texto en el lienzo: mitad del flanco, proporcional al radio exterior del anillo
    flanco: new THREE.MeshStandardMaterial({ map: texturaFlanco(512 * ((R_LLANTA - 0.078 - 0.02 + 0.012 + R_LLANTA - 0.035) / 2) / (R_LLANTA - 0.035)),
      transparent: true, alphaTest: 0.3, roughness: 0.6, side: THREE.DoubleSide }),
    rin: new THREE.MeshPhysicalMaterial({ color: 0x0c0d10, metalness: 0.6, roughness: 0.25, clearcoat: 0.8 }),
    disco: new THREE.MeshStandardMaterial({ map: texturaDisco(), alphaTest: 0.5, metalness: 0.9, roughness: 0.32,
      side: THREE.DoubleSide }),
    pinza: new THREE.MeshStandardMaterial({ color: 0xb8862b, metalness: 0.85, roughness: 0.3 }),
    resorte: new THREE.MeshStandardMaterial({ color: 0xffd23f, metalness: 0.4, roughness: 0.35 }),
    cupula: new THREE.MeshPhysicalMaterial({ color: 0x6f86a3, transparent: true, opacity: 0.24, roughness: 0.02,
      metalness: 0.1, clearcoat: 1, side: THREE.DoubleSide }),
    liquido: new THREE.MeshPhysicalMaterial({ color: 0xf5e6a8, transparent: true, opacity: 0.7, roughness: 0.1 }),
  };
  const xf = ejes / 2, xt = -ejes / 2;

  // --- carenado principal: la nariz va encima de la rueda delantera y el costado la rodea por detrás
  // (arco a 4 cm de la llanta, así la rueda puede girar y se ven la horquilla y los frenos)
  const arco = [180, 150, 125, 100, 75, 55, 40].map((g) => {
    const a = (g * Math.PI) / 180;
    return [xf + Math.cos(a) * (R_LLANTA + 0.04), R_LLANTA + Math.sin(a) * (R_LLANTA + 0.04)];
  });
  const carenado = pieza([[1.07, 0.68], [1.03, 0.78], [0.95, 0.86], [0.8, 0.92], [0.62, 0.93], [0.46, 0.87], [0.3, 0.79],
    [0.16, 0.71], [0.03, 0.62], [-0.05, 0.52], [-0.04, 0.4], [0.08, 0.31], [0.26, 0.27], ...arco, [1.02, 0.6]], 0.42,
  mats.pintura, { bisel: 0.045, afinar: (x, y) => afinado({ xNariz: 0.4, puntaNariz: 0.22, xMax: 1.07 })(x) * (y > 0.84 ? 0.86 : 1),
    lados: LADOS_CARENADO });
  grupo.add(carenado);
  // Quilla inferior de carbono, bajo el motor
  grupo.add(pieza([[0.37, 0.3], [0.27, 0.2], [0.0, 0.16], [-0.14, 0.22], [-0.12, 0.36], [0.08, 0.3]], 0.28, mats.carbono,
    { bisel: 0.035, afinar: afinado({ xCola: -0.02, puntaCola: 0.8, xMin: -0.14 }) }));
  // Tanque
  grupo.add(pieza([[0.48, 0.88], [0.3, 0.99], [0.05, 1.02], [-0.18, 0.96], [-0.25, 0.86], [0.0, 0.83], [0.4, 0.84]], 0.38,
    mats.azul, { bisel: 0.06, afinar: afinado({ xNariz: 0.25, puntaNariz: 0.7, xMax: 0.48, xCola: -0.05, puntaCola: 0.72, xMin: -0.25 }) }));
  // Franja amarilla sobre el tanque
  const franja = malla(new THREE.BoxGeometry(0.42, 0.006, 0.05), mats.filete, 0.08, 1.012, 0);
  franja.rotation.z = -0.05;
  grupo.add(franja);
  // Asiento de gamuza y colín afilado
  grupo.add(pieza([[-0.24, 0.87], [-0.56, 0.9], [-0.62, 0.85], [-0.3, 0.83]], 0.27, mats.gamuza, { bisel: 0.02 }));
  grupo.add(pieza([[-0.5, 0.88], [-0.72, 0.99], [-1.02, 1.05], [-1.08, 0.99], [-0.88, 0.86], [-0.64, 0.75], [-0.46, 0.77]],
    0.3, mats.colin, { bisel: 0.035, afinar: afinado({ xCola: -0.65, puntaCola: 0.45, xMin: -1.08 }),
      lados: [-1.08, -0.46, 0.74, 1.06] }));
  // Bandeja de carbono bajo el colín
  grupo.add(pieza([[-0.62, 0.76], [-0.98, 0.93], [-1.0, 0.89], [-0.66, 0.7]], 0.2, mats.carbono, { bisel: 0.015 }));
  // Cúpula ahumada que sigue la línea de la nariz
  grupo.add(pieza([[0.98, 0.84], [0.87, 0.96], [0.72, 1.05], [0.63, 1.03], [0.78, 0.95], [0.93, 0.83]], 0.3, mats.cupula,
    { bisel: 0.01, afinar: afinado({ xNariz: 0.7, puntaNariz: 0.5, xMax: 0.98 }) }));

  // --- aerodinámica: dos alerones con perfil de ala a cada lado de la nariz, unidos por una placa
  const perfilAla = new THREE.Shape();
  perfilAla.moveTo(0.17, 0);
  perfilAla.bezierCurveTo(0.17, 0.012, 0.12, 0.016, 0.07, 0.012);
  perfilAla.lineTo(0, 0.004); perfilAla.lineTo(0, 0); perfilAla.lineTo(0.07, -0.004);
  perfilAla.bezierCurveTo(0.12, -0.006, 0.17, -0.006, 0.17, 0);
  for (const lado of [1, -1]) {
    for (const [y, x, largo] of [[0.64, 0.8, 0.13], [0.71, 0.84, 0.11]]) {
      const geo = new THREE.ExtrudeGeometry(perfilAla, { depth: largo, bevelEnabled: false, curveSegments: 10 });
      const ala = malla(geo, mats.carbono, x, y, lado > 0 ? 0.115 : -0.115 - largo);
      ala.rotation.z = -0.1;   // borde de ataque hacia abajo: empuja la nariz contra el piso
      grupo.add(ala);
    }
    const placa = pieza([[0.97, 0.655], [0.955, 0.715], [0.88, 0.73], [0.86, 0.645]], 0.006, mats.carbono, { bisel: 0.002 });
    placa.position.z = lado * 0.245;
    grupo.add(placa);
    // Estriberas
    grupo.add(malla(new THREE.BoxGeometry(0.06, 0.02, 0.07), mats.aluminio, -0.3, 0.4, lado * 0.2));
  }
  // Toma de aire frontal (ovalada, oscura) y faros LED en franja
  const toma = malla(new THREE.SphereGeometry(1, 24, 16), mats.negro, 1.045, 0.71, 0);
  toma.scale.set(0.03, 0.035, 0.07);
  grupo.add(toma);
  const faroMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 3 });
  for (const z of [0.055, -0.055]) {
    const f = malla(new THREE.BoxGeometry(0.05, 0.012, 0.045), faroMat, 1.0, 0.79, z);
    f.rotation.set(0, z > 0 ? -0.5 : 0.5, -0.35);
    grupo.add(f);
  }
  const luzFreno = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0xff1e1e, emissiveIntensity: 0.6 });
  grupo.add(malla(new THREE.BoxGeometry(0.03, 0.035, 0.12), luzFreno, -1.07, 0.99, 0));

  // --- chasis: largueros de aluminio, motor, basculante, amortiguador, cadena y escape
  for (const lado of [1, -1]) {
    // Larguero del chasis: del cabezal de dirección al eje del basculante
    grupo.add(pieza([[0.46, 0.82], [0.2, 0.76], [-0.08, 0.66], [-0.2, 0.5], [-0.12, 0.45], [0.02, 0.58], [0.4, 0.74]], 0.035,
      mats.aluminio, { bisel: 0.01 }).translateZ(lado * 0.15));
    // Basculante de aluminio que se afina hacia el eje trasero
    grupo.add(pieza([[-0.1, 0.475], [-0.45, 0.43], [xt - 0.015, 0.35], [xt - 0.035, 0.29], [xt + 0.03, 0.27], [-0.45, 0.35],
      [-0.1, 0.395]], 0.04, mats.aluminio, { bisel: 0.012 }).translateZ(lado * 0.125));
  }
  // Refuerzo superior del basculante (la "banana" del lado derecho)
  grupo.add(tubo([[-0.12, 0.49, 0.125], [-0.35, 0.53, 0.13], [-0.6, 0.42, 0.13]], 0.016, mats.aluminio, false, 24));
  grupo.add(malla(new THREE.BoxGeometry(0.06, 0.06, 0.26), mats.aluminio, -0.2, 0.43, 0));
  // Motor (cárter y tapas), casi oculto por el carenado
  const motor = malla(new THREE.BoxGeometry(0.42, 0.3, 0.3), mats.negro, 0.18, 0.42, 0);
  grupo.add(motor);
  for (const lado of [1, -1]) {
    const tapa = malla(new THREE.CylinderGeometry(0.09, 0.09, 0.03, 24), mats.metal, 0.05, 0.36, lado * 0.155);
    tapa.rotation.x = Math.PI / 2;
    grupo.add(tapa);
  }
  // Amortiguador trasero: cuerpo dorado y resorte amarillo en espiral
  grupo.add(barra([-0.2, 0.72, 0], [-0.3, 0.42, 0], 0.022, mats.dorado));
  const espiral = [];
  for (let k = 0; k <= 80; k++) {
    const t = k / 80, a = t * Math.PI * 2 * 7;
    espiral.push([-0.215 - 0.075 * t + Math.cos(a) * 0.0, 0.66 - 0.2 * t, 0]);
    espiral[k][0] += Math.cos(a) * 0.038; espiral[k][2] = Math.sin(a) * 0.038;
  }
  grupo.add(tubo(espiral, 0.007, mats.resorte, false, 240));
  // Cadena dorada (del piñón a la corona, lado izquierdo)
  const zc = -0.11, piñon = [-0.06, 0.38], rp = 0.05, rCorona = 0.1;
  const cadena = [];
  for (let k = 0; k <= 12; k++) { const a = Math.PI / 2 + (Math.PI * k) / 12; cadena.push([piñon[0] + Math.cos(a) * rp, piñon[1] + Math.sin(a) * rp, zc]); }
  for (let k = 0; k <= 12; k++) { const a = -Math.PI / 2 + (Math.PI * k) / 12; cadena.push([xt + Math.cos(a) * rCorona, R_LLANTA + Math.sin(a) * rCorona, zc]); }
  grupo.add(tubo(cadena, 0.007, mats.dorado, true, 160));
  grupo.add(malla(new THREE.CylinderGeometry(rp, rp, 0.012, 18), mats.metal, piñon[0], piñon[1], zc).rotateX(Math.PI / 2));
  // Escape de titanio: colector bajo el motor y silenciador que sube bajo el colín (lado derecho)
  grupo.add(tubo([[0.42, 0.3, 0.04], [0.2, 0.2, 0.09], [-0.1, 0.23, 0.15], [-0.36, 0.42, 0.17], [-0.52, 0.56, 0.17]], 0.034,
    mats.titanio, false, 80));
  grupo.add(barra([-0.5, 0.545, 0.17], [-0.92, 0.79, 0.17], 0.056, mats.titanioLiso, 0.062));
  for (const t of [0.15, 0.85]) {   // abrazaderas del silenciador
    const p = [-0.5 + (-0.42) * t, 0.545 + 0.245 * t, 0.17];
    grupo.add(barra(p, [p[0] - 0.012, p[1] + 0.007, 0.17], 0.064, mats.metal));
  }
  const boca = barra([-0.92, 0.79, 0.17], [-0.95, 0.808, 0.17], 0.062, mats.carbono, 0.064);
  grupo.add(boca);
  grupo.add(barra([-0.94, 0.802, 0.17], [-0.955, 0.811, 0.17], 0.04, mats.negro));

  // --- ruedas: la delantera cuelga de la horquilla (pivote de dirección)
  const ruedas = [];
  const RAKE = 0.42, eje = new THREE.Vector2(-Math.sin(RAKE), Math.cos(RAKE));
  for (const [x, delantera, ancho] of [[xf, true, 0.125], [xt, false, 0.19]]) {
    const pivote = new THREE.Group();
    pivote.position.set(x, R_LLANTA, 0);
    const giro = crearRueda(ancho, mats);
    pivote.add(giro);
    if (delantera) {
      // Dos discos flotantes con pinzas radiales doradas
      for (const lado of [1, -1]) {
        const d = crearDisco(0.165, mats);
        d.position.z = lado * 0.078;
        giro.add(d);
        const pinza = crearPinza(mats);
        const a = (150 * Math.PI) / 180;
        pinza.position.set(Math.cos(a) * 0.14, Math.sin(a) * 0.14, lado * 0.096);
        pinza.rotation.z = a + Math.PI / 2;
        pivote.add(pinza);
      }
      // Horquilla invertida: barras doradas arriba, botellas negras abajo, inclinadas (avance)
      const p = (t) => [eje.x * t, eje.y * t];
      for (const lado of [1, -1]) {
        const z = lado * 0.105;
        pivote.add(barra([...p(-0.02), z], [...p(0.24), z], 0.027, mats.negro));
        pivote.add(barra([...p(0.2), z], [...p(0.6), z], 0.036, mats.dorado));
      }
      for (const t of [0.44, 0.58]) {
        const tija = malla(new THREE.BoxGeometry(0.09, 0.03, 0.27), mats.aluminio, ...p(t), 0);
        tija.rotation.z = RAKE;
        pivote.add(tija);
      }
      // Semimanillares, puños, palanca de freno y depósito del líquido
      for (const lado of [1, -1]) {
        const [x0, y0] = p(0.55);
        pivote.add(barra([x0, y0, lado * 0.11], [x0 - 0.06, y0 - 0.04, lado * 0.27], 0.012, mats.negro));
        pivote.add(barra([x0 - 0.04, y0 - 0.027, lado * 0.2], [x0 - 0.06, y0 - 0.04, lado * 0.27], 0.018, mats.gamuza));
        pivote.add(barra([x0 + 0.02, y0 - 0.02, lado * 0.15], [x0 + 0.03, y0 - 0.03, lado * 0.26], 0.005, mats.metal));
      }
      const [xd, yd] = p(0.62);
      pivote.add(barra([xd, yd, 0.13], [xd, yd + 0.05, 0.13], 0.016, mats.liquido));
      // Guardabarros de carbono (no gira con la rueda)
      // (con la rotación, el ángulo θ del cilindro queda en φ = θ − 90° medido desde adelante: cubre de 35° a 120°)
      const guarda = new THREE.Mesh(new THREE.CylinderGeometry(R_LLANTA + 0.025, R_LLANTA + 0.025, 0.11, 32, 1, true,
        (125 * Math.PI) / 180, (85 * Math.PI) / 180), mats.carbono);
      guarda.rotation.x = Math.PI / 2;
      guarda.castShadow = true;
      pivote.add(guarda);
    } else {
      // Atrás: disco a la derecha, corona dorada a la izquierda, pinza fija al basculante
      const d = crearDisco(0.11, mats);
      d.position.z = 0.11;
      giro.add(d);
      const corona = crearCorona(rCorona, 40, mats.dorado);
      corona.position.z = zc;
      giro.add(corona);
      const pinza = crearPinza(mats);
      pinza.scale.setScalar(0.8);
      pinza.position.set(-0.03, -0.09, 0.128);
      pivote.add(pinza);
    }
    grupo.add(pivote);
    ruedas.push({ pivote, giro, delantera, radio: R_LLANTA });
  }

  const piloto = crearPiloto({
    traje: new THREE.MeshStandardMaterial({ color: 0x1a3fb8, roughness: 0.5, metalness: 0.15 }),
    trajeAzul: new THREE.MeshStandardMaterial({ color: 0x0b1d5c, roughness: 0.5, metalness: 0.15 }),
    trajeBlanco: new THREE.MeshStandardMaterial({ color: 0xf1f3f6, roughness: 0.5 }),
    joroba: new THREE.MeshPhysicalMaterial({ color: 0xc9a227, metalness: 0.6, roughness: 0.3, clearcoat: 0.6 }),
    casco: new THREE.MeshPhysicalMaterial({ map: texturaCasco(), metalness: 0.2, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.03 }),
    visera: new THREE.MeshPhysicalMaterial({ color: 0x101827, metalness: 0.6, roughness: 0.04, clearcoat: 1,
      iridescence: 1, iridescenceIOR: 1.6, iridescenceThicknessRange: [200, 600] }),
    guante: new THREE.MeshStandardMaterial({ color: 0x111318, roughness: 0.7 }),
    bota: new THREE.MeshStandardMaterial({ color: 0xe8eaee, roughness: 0.45, metalness: 0.1 }),
    deslizador: new THREE.MeshStandardMaterial({ color: 0xffd23f, roughness: 0.4 }),
  });
  grupo.add(piloto);

  const faro = new THREE.SpotLight(0xfff3c4, 0, 60, 0.4, 0.6, 1.2);
  faro.position.set(L / 2, 0.7, 0);
  faro.target.position.set(L / 2 + 10, 0, 0);
  grupo.add(faro, faro.target);
  return { grupo, ruedas, luzFreno, faro, piloto };
}
