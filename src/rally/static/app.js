// Visor 3D de Autonomous Rally.
// El servidor (Python) corre el ambiente y manda cada paso; aquí solo se dibuja.
// Coordenadas: simulador (x, y) en metros -> three.js (x, altura, -y).

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { construirEscenario, tramoTunel } from "./escenario.js";
import { crearCarro, crearHumo } from "./carro.js";
import { pbr, cargas } from "./texturas.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { FXAAShader } from "three/addons/shaders/FXAAShader.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";

const $ = (id) => document.getElementById(id);
const API = globalThis.RALLY_API ?? "";  // vacío en el visor local; la URL de la API en Vercel
const P = (x, y, h = 0) => new THREE.Vector3(x, h, -y);
const lerp = (a, b, t) => a + (b - a) * t;
const lerpAng = (a, b, t) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * t;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const params = new URLSearchParams(location.search);
const SIN = new Set((params.get("sin") || "").split(","));   // diagnóstico de rendimiento
const PISTA_PEDIDA = (params.get("pista") || "monaco").toLowerCase();   // ?pista=bosque

// Si algo falla, se muestra en la pantalla de carga en vez de quedarse girando
function mostrarError(msg) {
  const t = document.getElementById("cargando-txt");
  if (t) { t.textContent = "Error: " + msg; t.style.color = "#fb7185"; }
}
addEventListener("error", (e) => mostrarError(`${e.message} (${(e.filename || "").split("/").pop()}:${e.lineno})`));
addEventListener("unhandledrejection", (e) => mostrarError(e.reason && (e.reason.stack || e.reason.message) || String(e.reason)));

let pista, ep = null;
const alcance = () => (ep ? ep.params.r_max : pista.rayos.alcance);
let reproduciendo = true, velocidad = 1, tiempo = 0, camara = params.get("cam") || "persecucion";
let listo = false;   // false mientras se prepara el escenario detrás de la pantalla de carga
let mu = parseFloat(params.get("mu") || "0.9");

// ------------------------------------------------------------------ escena
// El antialiasing lo hace el post-procesado (MSAA o FXAA), no el lienzo.
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });

// Niveles de calidad. "auto" elige según la tarjeta gráfica: en gráficos integrados
// (Intel, móviles) usa "media" para mantener la resolución al 100 % y buenos FPS.
const PRESETS = {
  alta:  { nombre: "Alta",  px: 1.25, msaa: 4, fxaa: false, bloom: true,  sombras: 2048, cadaSombra: 1, ao: true },
  media: { nombre: "Media", px: 1.0,  msaa: 0, fxaa: true,  bloom: false, sombras: 1024, cadaSombra: 2, ao: false },
  baja:  { nombre: "Baja",  px: 0.8,  msaa: 0, fxaa: true,  bloom: false, sombras: 0,    cadaSombra: 1, ao: false },
};
const GPU = (() => {
  const gl = renderer.getContext(), ext = gl.getExtension("WEBGL_debug_renderer_info");
  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "";
})();
const INTEGRADA = /intel|uhd|iris|mali|adreno|powervr|swiftshader|apple gpu/i.test(GPU);
let eleccion = params.get("calidad");
try { eleccion = eleccion || localStorage.getItem("rally-calidad"); } catch (e) { /* sin almacenamiento */ }
eleccion = PRESETS[eleccion] ? eleccion : "auto";
const CALIDAD = eleccion === "auto" ? (INTEGRADA ? "media" : "alta") : eleccion;
const Q = PRESETS[CALIDAD];

let resolucion = Math.min(devicePixelRatio, Q.px);
renderer.setPixelRatio(resolucion);
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = Q.sombras > 0;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = Q.cadaSombra === 1;   // en "media" las sombras se recalculan un cuadro sí, uno no
// AgX: colores más naturales que ACES (que satura el atardecer hacia naranja)
renderer.toneMapping = params.get("tono") === "aces" ? THREE.ACESFilmicToneMapping : THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
$("escena").appendChild(renderer.domElement);

const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.1, 4000);
cam.position.set(0, 60, 70);
// Post-procesado: MSAA (alta) o FXAA (media/baja), brillo suave (bloom) y gradación de color
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(innerWidth, innerHeight,
  { samples: Q.msaa, type: THREE.HalfFloatType }));
composer.addPass(new RenderPass(scene, cam));
// Oclusión ambiental: oscurece donde las cosas se tocan (llantas en el asfalto, público
// en las gradas, base de los muros). Da el "peso" de los juegos AAA; solo en Alta.
if (Q.ao && !SIN.has("ao")) {
  const ao = new GTAOPass(scene, cam, innerWidth, innerHeight);
  ao.updateGtaoMaterial({ radius: 0.8, distanceExponent: 1.5, thickness: 1.5, scale: 1.0, samples: 8 });
  ao.blendIntensity = 0.85;
  // El pase de normales del AO dibuja todo sólido: las hojas, la malla y el humo darían halos
  const ocultarBase = ao.overrideVisibility.bind(ao);
  ao.overrideVisibility = () => {
    ocultarBase();
    scene.traverse((o) => {
      const m = o.material;
      if (m && !Array.isArray(m) && (m.transparent || m.alphaTest > 0)) o.visible = false;
    });
  };
  composer.addPass(ao);
}
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.16, 0.5, 0.95);
if (Q.bloom) composer.addPass(bloom);
composer.addPass(new OutputPass());
// Gradación de color como una transmisión de TV: contraste en curva S, sombras un poco
// frías y luces cálidas, viñeta suave y grano fino de cámara
const gradacion = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, contraste: { value: 1.1 }, saturacion: { value: 1.18 }, vineta: { value: 0.28 },
    grano: { value: 0.035 }, tiempo: { value: 0 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float contraste, saturacion, vineta, grano, tiempo; varying vec2 vUv;
    void main(){
      vec4 c = texture2D(tDiffuse, vUv);
      float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
      c.rgb = mix(vec3(l), c.rgb, saturacion);
      vec3 s = clamp(c.rgb, 0.0, 1.0);
      c.rgb = mix(s, s * s * (3.0 - 2.0 * s), contraste - 1.0);            // curva S
      c.rgb += vec3(-0.012, 0.0, 0.016) * (1.0 - l) + vec3(0.014, 0.006, -0.01) * l;   // tonos fríos/cálidos
      float d = distance(vUv, vec2(0.5));
      c.rgb *= 1.0 - vineta * smoothstep(0.35, 0.9, d);
      // Ruido de gradiente intercalado (estable en GPUs Intel, sin patrones)
      vec2 px = gl_FragCoord.xy + vec2(tiempo * 37.0, tiempo * 17.0);
      float r = fract(52.9829189 * fract(dot(px, vec2(0.06711056, 0.00583715))));
      c.rgb += (r - 0.5) * grano * (1.0 - l * 0.6);
      gl_FragColor = c;
    }`,
});
// FXAA: suaviza bordes casi sin costo (en vez de MSAA x4, caro en gráficos integrados)
const fxaa = new ShaderPass(FXAAShader);
const ajustarFxaa = () => fxaa.material.uniforms.resolution.value.set(1 / (innerWidth * resolucion), 1 / (innerHeight * resolucion));
if (Q.fxaa) { composer.addPass(fxaa); ajustarFxaa(); }
composer.addPass(gradacion);   // después del FXAA: así no emborrona el grano
let cuadro = 0, hudAcum = 0;
const controles = new OrbitControls(cam, renderer.domElement);
controles.enableDamping = true;
controles.maxPolarAngle = Math.PI * 0.48;
controles.enabled = false;

const hemi = new THREE.HemisphereLight(0xcfe8ff, 0x3b5d2a, 0.9);
scene.add(hemi);
const sol = new THREE.DirectionalLight(0xfff1dc, 2.4);
sol.name = "sol";
sol.position.set(-60, 90, 40);
sol.castShadow = true;
sol.castShadow = Q.sombras > 0;
sol.shadow.mapSize.set(Q.sombras || 512, Q.sombras || 512);
Object.assign(sol.shadow.camera, { left: -75, right: 75, top: 75, bottom: -75, near: 10, far: 260 });
sol.shadow.bias = -0.0004;
sol.shadow.normalBias = 0.04;
scene.add(sol);

function cielo(arriba, abajo) {
  const c = document.createElement("canvas");
  c.width = 4; c.height = 512;
  const g = c.getContext("2d");
  const grad = g.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, arriba);
  grad.addColorStop(0.55, abajo);
  grad.addColorStop(1, abajo);
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ------------------------------------------------------------------ texturas
function texturaCesped() {
  const c = document.createElement("canvas");
  c.width = 1000; c.height = 700;
  const g = c.getContext("2d");
  for (let i = 0; i < 17; i++) {
    g.fillStyle = i % 2 ? "#5b9a3c" : "#4f8a34";
    g.fillRect(i * 60, 0, 60, 700);
  }
  for (let i = 0; i < 9000; i++) {
    g.fillStyle = `rgba(${Math.random() < .5 ? "20,60,10" : "160,210,110"},${Math.random() * .12})`;
    g.fillRect(Math.random() * 1000, Math.random() * 700, 2, 2);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function texturaAsfalto() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d");
  g.fillStyle = "#3a3d43";
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 6000; i++) {
    const v = 40 + Math.random() * 50;
    g.fillStyle = `rgba(${v},${v},${v + 4},${Math.random() * .5})`;
    g.fillRect(Math.random() * 256, Math.random() * 256, 1.5, 1.5);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function texturaTexto(texto, fondo = "#0f172a", color = "#fff", w = 256, h = 96) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d");
  g.fillStyle = fondo;
  g.beginPath(); g.roundRect(0, 0, w, h, 18); g.fill();
  g.fillStyle = color;
  g.font = `800 ${h * 0.58}px Inter, Arial`;
  g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(texto, w / 2, h / 2 + 3);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function texturaCuadros(nx = 12, ny = 2) {
  const c = document.createElement("canvas");
  c.width = nx * 32; c.height = ny * 32;
  const g = c.getContext("2d");
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
    g.fillStyle = (i + j) % 2 ? "#111" : "#f5f5f5";
    g.fillRect(i * 32, j * 32, 32, 32);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.magFilter = THREE.NearestFilter;
  return t;
}

// Vallas publicitarias del muro: 8 tableros de 6 m (u = s / 48 m)
function texturaVallas() {
  const marcas = [["AUTONOMOUS RALLY", "#0b1d5c", "#ffd23f"], ["MLflow", "#f8fafc", "#0194e2"], ["DVC", "#13adc7", "#ffffff"],
    ["PPO · RED NEURONAL", "#111827", "#f97316"], ["Gymnasium", "#7c3aed", "#ffffff"], ["three.js", "#000000", "#ffffff"],
    ["Hugging Face", "#ffd21e", "#111827"], ["DagsHub", "#16a34a", "#ffffff"]];
  const c = document.createElement("canvas");
  c.width = 4096; c.height = 128;
  const g = c.getContext("2d");
  marcas.forEach(([txt, fondo, letra], i) => {
    const x = i * 512;
    g.fillStyle = fondo; g.fillRect(x, 0, 512, 128);
    g.fillStyle = "rgba(255,255,255,0.12)"; g.fillRect(x, 0, 512, 10);
    g.fillStyle = letra; g.font = "italic 900 64px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
    g.save(); g.translate(x + 256, 68); g.scale(0.62, 1); g.fillText(txt, 0, 0); g.restore();
    g.fillStyle = "rgba(0,0,0,0.25)"; g.fillRect(x + 509, 0, 3, 128);
  });
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.anisotropy = 8;
  return t;
}

// Malla metálica de seguridad: 4 × 4 rombos de alambre por baldosa (6 cm cada rombo).
// De lejos los mipmaps la vuelven una gasa casi transparente, como una malla real.
function texturaMalla() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d");
  g.strokeStyle = "#d4d8de"; g.lineWidth = 3.4;
  for (let i = -4; i <= 4; i++) {
    g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64 + 256, 256); g.stroke();
    g.beginPath(); g.moveTo(i * 64 + 256, 0); g.lineTo(i * 64, 256); g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  return t;
}

// Goma en la línea de carrera: más oscura en el centro de la franja, con vetas
function texturaGoma() {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 256;
  const g = c.getContext("2d");
  for (let x = 0; x < 64; x++) {
    const a = Math.pow(Math.sin((x / 63) * Math.PI), 1.6) * 0.5;
    for (let y = 0; y < 256; y += 2) {
      g.fillStyle = `rgba(8,8,10,${a * (0.65 + Math.random() * 0.35)})`;
      g.fillRect(x, y, 1, 2);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// Oscurece y aclara el material en manchas grandes según la posición en el mundo
// (ruido en el shader): rompe la repetición de las texturas fotográficas.
function macroVariacion(mat, escala, fuerza) {
  mat.onBeforeCompile = (sh) => {
    sh.vertexShader = "varying vec3 vMundo;\n" + sh.vertexShader.replace("#include <worldpos_vertex>",
      "#include <worldpos_vertex>\n  vMundo = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    sh.fragmentShader = `varying vec3 vMundo;
float hashM(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float ruidoM(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hashM(i), hashM(i + vec2(1, 0)), f.x), mix(hashM(i + vec2(0, 1)), hashM(i + vec2(1, 1)), f.x), f.y); }
` + sh.fragmentShader.replace("#include <map_fragment>", `#include <map_fragment>
  { vec2 p = vMundo.xz * ${escala.toFixed(4)};
    float v = ruidoM(p) * 0.6 + ruidoM(p * 3.1) * 0.3 + ruidoM(p * 9.7) * 0.1;
    diffuseColor.rgb *= 1.0 + (v - 0.5) * ${(fuerza * 2).toFixed(3)}; }`);
  };
  mat.customProgramCacheKey = () => "macro" + escala + fuerza;
}

// ------------------------------------------------------------------ pista
// Texturas fotográficas (Poly Haven, CC0): asfalto de circuito y pasto en el escape
const matAsfalto = new THREE.MeshStandardMaterial({ map: texturaAsfalto(), roughness: 0.9, metalness: 0.0 });
pbr(matAsfalto, "asphalt_track", { repetir: [2, 1], relieve: 0.6, res: CALIDAD === "alta" ? "2k" : "1k" });
// Parches grandes (reparaciones, desgaste): la foto se repite cada 4 m y sin esto se nota
macroVariacion(matAsfalto, 0.045, 0.28);
const matEscape = new THREE.MeshStandardMaterial({ color: 0x4f7a34, roughness: 1 });
pbr(matEscape, "leafy_grass", { repetir: [1, 1] });
const matVallas = new THREE.MeshStandardMaterial({ map: texturaVallas(), roughness: 0.45 });
const matArmco = new THREE.MeshStandardMaterial({ color: 0xc3c8cf, metalness: 0.85, roughness: 0.3 });
const matMalla = new THREE.MeshStandardMaterial({ map: texturaMalla(), transparent: true, depthWrite: false,
  side: THREE.DoubleSide, color: 0xc9ced6, metalness: 0.7, roughness: 0.35 });
// Mate y sin reflejo en seco: si refleja el cielo, la goma se ve más clara que el asfalto
const matGoma = new THREE.MeshStandardMaterial({ map: texturaGoma(), transparent: true, depthWrite: false, roughness: 1,
  envMapIntensity: 0, polygonOffset: true, polygonOffsetFactor: -2 });
// Pianitos (color por vértice + relieve del asfalto) y pintura del borde
const matPiano = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5 });
pbr(matPiano, "asphalt_track", { repetir: [1, 1], relieve: 0.3, color: false, res: CALIDAD === "alta" ? "2k" : "1k" });
const matLinea = new THREE.MeshStandardMaterial({ color: 0xf1f1ee, roughness: 0.55 });
const puertas = [];

// Cinta a lo largo de la línea central entre dos desvíos laterales (+ = izquierda).
// `altura` puede ser [en offA, en offB] (cinta inclinada) y los desvíos pueden ser
// funciones del índice (cinta que se mueve, como la línea de carrera).
function cinta(offA, offB, altura, colorPorS = null, incluir = null) {
  const c = pista.centro, n = c.length;
  const pos = [], col = [], uv = [];
  const [hA, hB] = Array.isArray(altura) ? altura : [altura, altura];
  const valor = (f, k) => (typeof f === "function" ? f(k % n) : f);
  const punto = (k, off, alt) => {
    const [, x, y, h] = c[k % n], o = valor(off, k);
    return P(x - Math.sin(h) * o, y + Math.cos(h) * o, alt);
  };
  // Si offA queda a la derecha de offB los triángulos quedarían boca abajo (invisibles): se ordenan
  const [oA, oB, alA, alB] = valor(offA, 0) <= valor(offB, 0) ? [offA, offB, hA, hB] : [offB, offA, hB, hA];
  for (let i = 0; i < n; i++) {
    if (incluir && !incluir(i)) continue;
    const a1 = punto(i, oA, alA), b1 = punto(i, oB, alB), a2 = punto(i + 1, oA, alA), b2 = punto(i + 1, oB, alB);
    // Orden de vértices con la cara hacia arriba (el eje y se invierte al pasar a three.js)
    for (const p of [a1, a2, b1, b1, a2, b2]) pos.push(p.x, p.y, p.z);
    const s = c[i][0];
    uv.push(0, s / 4, 0, (s + .5) / 4, 1, s / 4, 1, s / 4, 0, (s + .5) / 4, 1, (s + .5) / 4);
    if (colorPorS) {
      const k = new THREE.Color(colorPorS(s));
      for (let j = 0; j < 6; j++) col.push(k.r, k.g, k.b);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  if (colorPorS) geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  geo.computeVertexNormals();
  return geo;
}

// Pared vertical a lo largo de la pista, a `off` metros del centro, entre dos alturas.
// uv: u = s / largoU (a lo largo), v = 0..altoV (de abajo a arriba)
function pared(off, h0, h1, colorPorS, largoU = 48, altoV = 1) {
  const c = pista.centro, n = c.length, pos = [], col = [], uv = [];
  const k = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const [s, x, y, h] = c[i], [s2, x2, y2, h2] = c[(i + 1) % n];
    const sb = s2 < s ? pista.largo : s2;
    const a = P(x - Math.sin(h) * off, y + Math.cos(h) * off), b = P(x2 - Math.sin(h2) * off, y2 + Math.cos(h2) * off);
    const q = [[a, h0, s, 0], [b, h0, sb, 0], [a, h1, s, 1], [a, h1, s, 1], [b, h0, sb, 0], [b, h1, sb, 1]];
    k.set(colorPorS(s));
    for (const [p, hh, ss, vv] of q) { pos.push(p.x, hh, p.z); col.push(k.r, k.g, k.b); uv.push(ss / largoU, vv * altoV); }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  geo.computeVertexNormals();
  return geo;
}

// La pista (asfalto, pianitos, línea central y puertas) depende del ancho del
// experimento, así que se reconstruye cuando cambia. Lo demás se crea una vez.
let grupoPista = null, anchoConstruido = null, fondoMini = null;
function construirPista(w) {
  if (grupoPista) {
    scene.remove(grupoPista);
    grupoPista.traverse((o) => o.geometry && o.geometry.dispose());
  }
  grupoPista = new THREE.Group();
  puertas.length = 0;
  anchoConstruido = w;
  fondoMini = null;

  const asfalto = new THREE.Mesh(cinta(-w / 2, w / 2, 0.02), matAsfalto);
  asfalto.receiveShadow = true;
  grupoPista.add(asfalto);
  // Curvatura suavizada (±15 m): dónde hay curva y hacia qué lado
  const c = pista.centro, n = c.length, paso = pista.largo / n;
  const ventana = Math.max(1, Math.round(15 / paso));
  const kSuave = c.map((_, i) => {
    let t = 0;
    for (let j = -ventana; j <= ventana; j++) t += c[(i + j + n) % n][4];
    return t / (2 * ventana + 1);
  });
  // Pianitos con relieve (suben 5 cm hacia afuera), rojo y blanco cada metro, solo en las curvas.
  // Histéresis: la curva "empieza" con κ > 1/90 y "termina" con κ < 1/130 (sin trocitos sueltos).
  const colorPiano = (s) => (Math.floor(s) % 2 ? 0xc81e1e : 0xf3f3f1);
  const curva = new Array(n).fill(false);
  let dentro = false;
  for (let pasada = 0; pasada < 2; pasada++) {      // dos vueltas: la curva que cruza la meta queda bien
    for (let i = 0; i < n; i++) {
      const k = Math.abs(kSuave[i]);
      dentro = dentro ? k > 1 / 130 : k > 1 / 90;
      if (pasada === 1) curva[i] = dentro;
    }
  }
  const enCurva = (i) => curva[i];
  for (const lado of [-1, 1]) {
    const borde0 = lado * (w / 2 - 0.75), borde1 = lado * (w / 2 + 0.5), medio = lado * (w / 2 - 0.1);
    for (const [a, b, ha, hb] of [[borde0, medio, 0.022, 0.07], [medio, borde1, 0.07, 0.04]]) {
      const m = new THREE.Mesh(cinta(a, b, [ha, hb], colorPiano, enCurva), matPiano);
      m.receiveShadow = true;
      grupoPista.add(m);
    }
  }
  // Líneas blancas del borde de la pista (pintura)
  for (const lado of [-1, 1]) {
    grupoPista.add(new THREE.Mesh(cinta(lado * (w / 2 - 0.32), lado * (w / 2 - 0.2), 0.026), matLinea));
  }
  // Goma de la línea de carrera: por fuera antes de la curva, pegada adentro en el vértice
  // y otra vez por fuera a la salida (curvatura aquí menos la de 20 m antes y después)
  const L = Math.round(20 / paso), kk = (i) => kSuave[((i % n) + n) % n];
  const linea = (i) => clamp(40 * kk(i) - 30 * (kk(i + L) + kk(i - L)) / 2, -1, 1) * (w / 2 - 1.7);
  const goma = new THREE.Mesh(cinta((i) => linea(i) - 1.0, (i) => linea(i) + 1.0, 0.024), matGoma);
  goma.receiveShadow = true;
  grupoPista.add(goma);

  // Zona de escape (pasto) y muros a ambos lados, igual que en el simulador
  const borde = w / 2 + pista.escape;
  for (const [a, b] of [[-borde, -w / 2 - 0.4], [w / 2 + 0.4, borde]]) {
    const m = new THREE.Mesh(cinta(a, b, 0.012), matEscape);
    m.receiveShadow = true;
    grupoPista.add(m);
  }
  // Muro: vallas publicitarias + baranda Armco metálica + malla de seguridad con postes
  const blanco = () => 0xffffff;
  for (const lado of [-1, 1]) {
    const off = lado * (borde + 0.15);
    for (const [geo, mat, sombra] of [
      [pared(off, 0, 1.0, blanco), matVallas, true],
      [pared(off, 1.0, 1.32, blanco, 4), matArmco, true],
      [pared(off + lado * 0.12, 1.32, 4.4, blanco, 0.24, 12.8), matMalla, false],
    ]) {
      const muro = new THREE.Mesh(geo, mat);
      muro.castShadow = sombra;
      muro.receiveShadow = true;
      grupoPista.add(muro);
    }
  }
  const lugaresPoste = [];
  for (let k = 0; k < pista.centro.length; k += 8) {
    const [, x, y, h] = pista.centro[k];
    for (const lado of [-1, 1]) lugaresPoste.push(P(x - Math.sin(h) * lado * (borde + 0.27), y + Math.cos(h) * lado * (borde + 0.27), 2.6));
  }
  const matPoste = new THREE.MeshStandardMaterial({ color: 0x6b7178, metalness: 0.55, roughness: 0.45 });
  const postes = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.035, 0.04, 3.4, 6), matPoste, lugaresPoste.length);
  lugaresPoste.forEach((p, i) => postes.setMatrixAt(i, new THREE.Matrix4().makeTranslation(p.x, p.y, p.z)));
  postes.castShadow = true;
  grupoPista.add(postes);

  // Puertas: checkpoints y meta
  for (const pu of pista.puertas) {
    const g = new THREE.Group();
    g.position.copy(P(pu.x, pu.y));
    g.rotation.y = pu.h;
    const esMeta = pu.nombre === "META";
    const mat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 0.6, roughness: 0.4 });
    const ancho = w + 1.2;
    for (const z of [-ancho / 2, ancho / 2]) {
      const poste = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.28, 4.4, 16), mat);
      poste.position.set(0, 2.2, z);
      poste.castShadow = true;
      g.add(poste);
    }
    const viga = new THREE.Mesh(new THREE.BoxGeometry(0.5, esMeta ? 1.2 : 0.55, ancho + 0.4),
      esMeta ? new THREE.MeshStandardMaterial({ map: texturaCuadros(16, 2), roughness: 0.5 }) : mat);
    viga.position.set(0, esMeta ? 4.4 : 4.3, 0);
    viga.castShadow = true;
    g.add(viga);
    const cartel = new THREE.Sprite(new THREE.SpriteMaterial({ map: texturaTexto(pu.nombre), depthTest: true }));
    cartel.scale.set(3.4, 1.28, 1);
    cartel.position.set(0, esMeta ? 5.9 : 5.4, 0);
    g.add(cartel);
    if (esMeta) {
      const suelo = new THREE.Mesh(new THREE.PlaneGeometry(1.6, w), new THREE.MeshStandardMaterial({ map: texturaCuadros(2, 10), roughness: 0.7 }));
      suelo.rotation.x = -Math.PI / 2;
      suelo.position.y = 0.04;
      suelo.receiveShadow = true;
      g.add(suelo);
    } else {
      const franja = new THREE.Mesh(new THREE.PlaneGeometry(0.5, w),
        new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.55 }));
      franja.rotation.x = -Math.PI / 2;
      franja.position.y = 0.045;
      g.add(franja);
      g.userData.franja = franja;
    }
    g.userData.mat = mat;
    g.userData.id = pu.id;
    grupoPista.add(g);
    puertas.push(g);
  }
  scene.add(grupoPista);
}

// Escenario (cielo, mar, ciudad, público, túnel...) en escenario.js
let escenario = null;
function construirMundo() {
  escenario = construirEscenario({ scene, renderer, pista, P, pared, cinta });
}

// ------------------------------------------------------------------ carro
const carro = new THREE.Group();
const ruedas = [];
let luzFreno, faro;

let humo = null;
function construirCarro() {
  // Cuando carga el modelo realista, sus ruedas reemplazan a las del carro básico
  const c = crearCarro(pista.carro, { calidad: CALIDAD, alCargar: (nuevas) => { ruedas.length = 0; ruedas.push(...nuevas); } });
  carro.add(c.grupo);
  ruedas.push(...c.ruedas);
  luzFreno = c.luzFreno;
  faro = c.faro;
  scene.add(carro);
  carro.visible = !SIN.has("carro");
  humo = crearHumo(scene);
}

// ------------------------------------------------------------------ rayos
const rayos = [];
function construirRayos() {
  for (let i = 0; i < pista.rayos.angulos.length; i++) {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const linea = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.9, toneMapped: false }));
    const punta = new THREE.Mesh(new THREE.SphereGeometry(0.11, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0x22d3ee, toneMapped: false }));
    const anillo = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.24, 24),
      new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.7, side: THREE.DoubleSide, toneMapped: false }));
    anillo.rotation.x = -Math.PI / 2;
    scene.add(linea, punta, anillo);
    rayos.push({ linea, punta, anillo });
  }
}

const colorRayo = new THREE.Color();
function colorDistancia(d) {
  const f = clamp(d / alcance(), 0, 1);
  if (f < 0.25) return colorRayo.setRGB(1, 0.2 + f * 2, 0.25);
  if (f < 0.55) return colorRayo.setRGB(1, 0.8, 0.15);
  return colorRayo.setRGB(0.13, 0.83, 0.93);
}

// ------------------------------------------------------------------ estela y derrapes
let estela, marcas, marcasPorFrame = [];
function construirEstela() {
  if (estela) { scene.remove(estela, marcas); estela.geometry.dispose(); marcas.geometry.dispose(); }
  const f = ep.frames, pos = [], col = [];
  const c = new THREE.Color();
  for (let i = 0; i < f.length - 1; i++) {
    const a = f[i], b = f[i + 1];
    const h = Math.atan2(b.y - a.y, b.x - a.x);
    const nx = -Math.sin(h) * 0.22, ny = Math.cos(h) * 0.22;
    const pts = [P(a.x + nx, a.y + ny, 0.06), P(a.x - nx, a.y - ny, 0.06), P(b.x + nx, b.y + ny, 0.06), P(b.x - nx, b.y - ny, 0.06)];
    for (const p of [pts[0], pts[1], pts[2], pts[1], pts[3], pts[2]]) pos.push(p.x, p.y, p.z);
    c.setHSL(0.75 - clamp(b.v / 25, 0, 1) * 0.25, 0.9, 0.62);
    for (let j = 0; j < 6; j++) col.push(c.r, c.g, c.b);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  estela = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85, depthWrite: false, toneMapped: false }));
  scene.add(estela);

  // Marcas de derrape en las ruedas traseras
  const mp = [];
  marcasPorFrame = [0];
  const W = pista.carro.ancho / 2, back = -pista.carro.ejes / 2;
  for (let i = 0; i < f.length - 1; i++) {
    const a = f[i], b = f[i + 1];
    if (b.derrape || b.fuera > 0) {
      for (const lado of [W, -W]) {
        const pa = rueda(a, back, lado), pb = rueda(b, back, lado);
        const h = Math.atan2(pb.y - pa.y, pb.x - pa.x), nx = -Math.sin(h) * 0.16, ny = Math.cos(h) * 0.16;
        const q = [P(pa.x + nx, pa.y + ny, 0.055), P(pa.x - nx, pa.y - ny, 0.055), P(pb.x + nx, pb.y + ny, 0.055), P(pb.x - nx, pb.y - ny, 0.055)];
        for (const p of [q[0], q[1], q[2], q[1], q[3], q[2]]) mp.push(p.x, p.y, p.z);
      }
    }
    marcasPorFrame.push(mp.length / 3);
  }
  const g2 = new THREE.BufferGeometry();
  g2.setAttribute("position", new THREE.Float32BufferAttribute(mp.length ? mp : [0, 0, 0], 3));
  marcas = new THREE.Mesh(g2, new THREE.MeshBasicMaterial({ color: 0x0a0a0a, transparent: true, opacity: 0.55, depthWrite: false }));
  scene.add(marcas);
}
function rueda(fr, lx, ly) {
  const c = Math.cos(fr.psi), s = Math.sin(fr.psi);
  return { x: fr.x + lx * c - ly * s, y: fr.y + lx * s + ly * c };
}

// ------------------------------------------------------------------ lluvia
let lluvia;
// Gotas como trazos cortos (líneas) que caen con algo de viento
const GOTA = 0.9;
function construirLluvia() {
  const N = 7000, pos = new Float32Array(N * 6);
  for (let i = 0; i < N; i++) {
    const x = (Math.random() * 2 - 1) * 75, y = Math.random() * 40, z = (Math.random() * 2 - 1) * 60;
    pos.set([x, y, z, x + 0.12, y + GOTA, z], i * 6);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  lluvia = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0xc7d8f0, transparent: true, opacity: 0.38, depthWrite: false }));
  lluvia.visible = false;
  lluvia.frustumCulled = false;
  scene.add(lluvia);
}

function aplicarClima() {
  const mojado = mu < 0.75;
  escenario.aplicarClima(mojado);
  hemi.intensity = mojado ? 0.25 : 0.3;
  hemi.color.set(mojado ? 0x9fb0c8 : 0xffd9a8);
  // Asfalto mojado: más oscuro y casi espejo (refleja el cielo y las luces)
  matAsfalto.roughness = mojado ? 0.18 : 1.0;
  matAsfalto.metalness = mojado ? 0.15 : 0.0;
  matAsfalto.color.set(mojado ? 0x6d727c : 0xffffff);
  matEscape.color.set(mojado ? 0x7f9a74 : 0xbfe0a0);   // pasto verde (la foto sola sale seca)
  // Pintura y pianitos mojados brillan; la goma casi no se nota bajo el agua
  matPiano.roughness = matLinea.roughness = mojado ? 0.15 : 0.5;
  matGoma.opacity = mojado ? 0.45 : 1;
  matGoma.roughness = mojado ? 0.2 : 1;
  matGoma.envMapIntensity = mojado ? 1 : 0;
  lluvia.visible = mojado;
  if (humo) humo.clima(mojado);
  faro.intensity = mojado ? 60 : 0;
  document.querySelectorAll("#sel-piso button").forEach((b) => b.classList.toggle("activo", parseFloat(b.dataset.mu) === mu));
  $("r-cambiar").textContent = mojado ? "Probar en seco" : "Probar con lluvia";
}

// ------------------------------------------------------------------ cámaras
const camObjetivo = new THREE.Vector3(), camMirar = new THREE.Vector3(), mirarSuave = new THREE.Vector3();
// Cámaras de TV: postes cada ~60 m a un costado de la pista, alternando lados
let camsTV = [], camsTunel = [], tunelTV = null;
function prepararCamsTV() {
  const c = pista.centro, paso = Math.round(60 / 0.5), muro = pista.ancho / 2 + pista.escape;
  camsTV = [];
  for (let i = 0; i < c.length; i += paso) {
    const [, x, y, h] = c[i], lado = (i / paso) % 2 ? 1 : -1, off = lado * (muro + 7);
    camsTV.push([x - Math.sin(h) * off, y + Math.cos(h) * off, 13]);   // sobre el techo de las graderías
  }
  // Desde los postes el túnel solo muestra el techo: adentro van cámaras contra la pared
  tunelTV = tramoTunel(pista);
  camsTunel = [];
  if (!tunelTV) return;
  for (let s = tunelTV[0] + 12, k = 0; s < tunelTV[1]; s += 30, k++) {
    const [, x, y, h] = c.find((p) => p[0] >= s), off = (k % 2 ? 1 : -1) * (muro - 0.3);
    camsTunel.push([x - Math.sin(h) * off, y + Math.cos(h) * off, 5.2]);
  }
}

function actualizarCamara(est, dt) {
  const dir = new THREE.Vector3(Math.cos(est.psi), 0, -Math.sin(est.psi));
  const pos = P(est.x, est.y);
  controles.enabled = camara === "libre";
  if (camara === "libre") { controles.update(); return; }
  let suave = 1 - Math.pow(0.0015, dt);
  if (camara === "persecucion") {
    camObjetivo.copy(pos).addScaledVector(dir, -10).add(new THREE.Vector3(0, 4.2, 0));
    camMirar.copy(pos).addScaledVector(dir, 5).add(new THREE.Vector3(0, 0.8, 0));
  } else if (camara === "cabina") {
    camObjetivo.copy(pos).addScaledVector(dir, -0.3).add(new THREE.Vector3(0, 1.35, 0));
    camMirar.copy(pos).addScaledVector(dir, 12).add(new THREE.Vector3(0, 0.9, 0));
    suave = 1;
  } else if (camara === "vitrina") {
    // Gira despacio alrededor del carro, a la altura de los ojos (como el menú de un videojuego)
    const ang = params.has("vang") ? +params.get("vang") : performance.now() / 1000 * 0.3;
    camObjetivo.copy(pos).add(new THREE.Vector3(Math.cos(ang) * 6.2, 1.5, Math.sin(ang) * 6.2));
    camMirar.copy(pos).add(new THREE.Vector3(0, 0.55, 0));
    suave = 1;
  } else if (camara === "aerea") {
    const [MX] = pista.mapa;
    camObjetivo.set(0, MX * 1.2, MX * 0.8);
    camMirar.set(0, 0, MX * 0.05);
    suave = 1 - Math.pow(1e-5, dt);
  } else if (camara === "tv") {
    const enTunel = tunelTV && est.s >= tunelTV[0] - 6 && est.s <= tunelTV[1] + 6;
    let mejor = camsTV[0], dmin = Infinity;
    for (const c of enTunel ? camsTunel : camsTV) {
      const d = Math.hypot(c[0] - est.x, c[1] - est.y);
      if (d < dmin) { dmin = d; mejor = c; }
    }
    camObjetivo.copy(P(mejor[0], mejor[1], mejor[2]));
    camMirar.copy(pos);
    if (cam.position.distanceTo(camObjetivo) > 5) { // corte de cámara
      cam.position.copy(camObjetivo);
      mirarSuave.copy(camMirar);
    }
    suave = 1;
    cam.fov = lerp(cam.fov, enTunel ? 50 : clamp(14 + dmin * 0.9, 18, 55), 0.08);
    cam.updateProjectionMatrix();
  }
  if (camara !== "tv" && cam.fov !== 55) { cam.fov = 55; cam.updateProjectionMatrix(); }
  cam.position.lerp(camObjetivo, suave);
  mirarSuave.lerp(camMirar, camara === "tv" ? 0.2 : suave);
  cam.lookAt(mirarSuave);
}

function ponerCamara(nombre) {
  camara = nombre;
  document.querySelectorAll("#camaras button").forEach((b) => b.classList.toggle("activo", b.dataset.cam === nombre));
  if (nombre === "libre") {
    const est = estado();
    if (est) controles.target.copy(P(est.x, est.y));
  }
  if (nombre === "aerea") mirarSuave.set(0, 0, 0);
}

// ------------------------------------------------------------------ estado interpolado
function estado() {
  if (!ep) return null;
  const f = ep.frames, dt = pista.dt;
  const i = clamp(Math.floor(tiempo / dt), 0, f.length - 1);
  const j = Math.min(i + 1, f.length - 1);
  const t = j === i ? 0 : clamp(tiempo / dt - i, 0, 1);
  const a = f[i], b = f[j];
  return {
    i, a, b,
    x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), psi: lerpAng(a.psi, b.psi, t),
    v: lerp(a.v, b.v, t), d: lerp(a.d, b.d, t), s: lerp(a.s, b.s, t),
    accion: b.a, agarre: lerp(a.agarre, b.agarre, t),
  };
}

// ------------------------------------------------------------------ HUD
const ARCO = 376.99; // largo del arco del velocímetro (270°, r = 80)
function prepararHUD() {
  const marcasG = $("marcas");
  for (let k = 0; k <= 9; k++) {
    const ang = (-225 + k * 30) * Math.PI / 180;
    const x1 = 100 + Math.cos(ang) * 64, y1 = 100 + Math.sin(ang) * 64;
    const x2 = 100 + Math.cos(ang) * 56, y2 = 100 + Math.sin(ang) * 56;
    marcasG.insertAdjacentHTML("beforeend", `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`);
    const tx = 100 + Math.cos(ang) * 46, ty = 100 + Math.sin(ang) * 46 + 3;
    marcasG.insertAdjacentHTML("beforeend", `<text x="${tx}" y="${ty}">${k * 10}</text>`);
  }
  $("arco-vel").style.strokeDasharray = `${ARCO}`;
  $("cps").innerHTML = pista.puertas.map((p) => `<span data-id="${p.id}">${p.nombre}</span>`).join("");
}

let ultimoAviso = "", ultimoCP = 1, avisoHasta = 0;
function aviso(texto, clase, ms = 0) {
  const el = $("aviso");
  if (texto) {
    el.textContent = texto;
    el.className = `visible ${clase}`;
    avisoHasta = ms ? performance.now() + ms : 0;
  } else if (!avisoHasta || performance.now() > avisoHasta) {
    el.className = "";
  }
  ultimoAviso = texto;
}

function actualizarHUD(est) {
  const { a, b } = est;
  const kmh = est.v * 3.6;
  $("i-kmh").textContent = kmh.toFixed(0);
  $("i-ms").textContent = `${est.v.toFixed(1)} m/s`;
  const fv = clamp(kmh / 90, 0, 1);
  $("arco-vel").style.strokeDashoffset = `${ARCO * (1 - fv)}`;
  $("aguja").style.transform = `rotate(${-135 + fv * 270}deg)`;

  const [acel, dir] = est.accion;
  $("i-acel").style.width = `${Math.max(0, acel) * 100}%`;
  $("i-freno").style.width = `${Math.max(0, -acel) * 100}%`;
  const grados = dir * pista.delta_max * 180 / Math.PI;
  $("volante").style.transform = `rotate(${-dir * 160}deg)`;
  $("i-dir").textContent = `${grados > 0.5 ? "◀ " : grados < -0.5 ? "" : ""}${Math.abs(grados).toFixed(0)}°${grados < -0.5 ? " ▶" : ""}`;

  const ag = clamp(est.agarre, 0, 1);
  const arco = $("i-agarre-arco");
  arco.style.strokeDashoffset = `${251.3 * (1 - ag)}`;
  arco.style.stroke = b.derrape ? "#e10600" : ag > 0.8 ? "#ffd23f" : "#2ee59d";
  $("i-agarre").textContent = b.derrape ? "MAX" : `${(ag * 100).toFixed(0)}%`;

  $("t-total").textContent = `${b.R >= 0 ? "+" : ""}${b.R.toFixed(1)}`;
  $("t-total").style.color = b.R >= 0 ? "#2ee59d" : "#ff4d45";
  $("t-paso").textContent = `${b.r >= 0 ? "+" : ""}${b.r.toFixed(2)}`;
  $("t-paso").style.color = b.r >= 0 ? "#2ee59d" : "#ff4d45";

  document.querySelectorAll("#cps span").forEach((el) => {
    const id = +el.dataset.id;
    el.className = id < b.cp ? "hecho" : id === b.cp ? "siguiente" : "";
  });
  const prog = clamp(est.s / pista.largo, 0, 1);
  $("t-progreso").style.width = `${prog * 100}%`;
  $("t-progreso-txt").textContent = `${(prog * 100).toFixed(0)}%`;

  const hw = anchoConstruido / 2;
  $("t-desvio").textContent = `${est.d >= 0 ? "+" : ""}${est.d.toFixed(1)} m`;
  $("t-desvio-punto").style.left = `${50 - clamp(est.d / hw, -2, 2) * 25}%`;

  // Estado y avisos
  const st = $("estado");
  if (b.fin === "exito") { st.textContent = "VUELTA COMPLETA"; st.className = "pastilla exito"; }
  else if (b.fin) { st.textContent = { choque: "CHOQUE", salida: "FUERA DE PISTA", estancado: "ESTANCADO", tiempo: "SIN TIEMPO" }[b.fin]; st.className = "pastilla mal"; }
  else if (b.fuera > 0) { st.textContent = `CÉSPED ${b.fuera.toFixed(1)}/1.0 s`; st.className = "pastilla alerta"; }
  else if (b.derrape) { st.textContent = "DERRAPE"; st.className = "pastilla alerta"; }
  else { st.textContent = "EN PISTA"; st.className = "pastilla ok"; }

  if (b.cp !== ultimoCP && b.cp > ultimoCP && b.cp <= 4) aviso(`✔ ${pista.puertas[b.cp - 2].nombre}  +10`, "cp", 1300);
  ultimoCP = b.cp;
  if (b.fuera > 0 && !b.fin) aviso("EN EL CÉSPED", "cesped");
  else if (b.derrape && !b.fin) aviso("DERRAPE · SUBVIRAJE", "derrape");
  else aviso("", "");

  $("reloj").textContent = `${b.t.toFixed(1)} / ${ep.tiempo.toFixed(1)} s`;
  $("barra").value = tiempo / ((ep.frames.length - 1) * pista.dt);

  dibujarRadar(b, est);
  dibujarGrafica(est.i);
  dibujarMinimapa(est);
}

// Lienzos del HUD a doble resolución (nítidos en pantallas con escala); W y H siguen en
// píxeles lógicos para que el dibujo no cambie.
function lienzo2D(cv) {
  if (!cv.dataset.w) {
    cv.dataset.w = cv.width; cv.dataset.h = cv.height;
    cv.width *= 2; cv.height *= 2;
  }
  const g = cv.getContext("2d");
  g.setTransform(2, 0, 0, 2, 0, 0);
  return [cv, g, +cv.dataset.w, +cv.dataset.h];
}

// Radar: los 7 rayos tal como los observa el agente
function dibujarRadar(b) {
  const [, g, W, H] = lienzo2D($("radar"));
  g.clearRect(0, 0, W, H);
  const cx = W / 2, cy = H - 18, R = H - 30, alc = alcance();
  g.strokeStyle = "rgba(148,163,184,.15)";
  for (const f of [0.25, 0.5, 0.75, 1]) { g.beginPath(); g.arc(cx, cy, R * f, Math.PI, 2 * Math.PI); g.stroke(); }
  pista.rayos.angulos.forEach((ang, k) => {
    const d = b.rayos[k], f = d / alc;
    const a = -Math.PI / 2 - ang;
    const ex = cx + Math.cos(a) * R * f, ey = cy + Math.sin(a) * R * f;
    const c = colorDistancia(d);
    const css = `rgb(${c.r * 255 | 0},${c.g * 255 | 0},${c.b * 255 | 0})`;
    g.strokeStyle = "rgba(148,163,184,.12)"; g.lineWidth = 1;
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); g.stroke();
    g.strokeStyle = css; g.lineWidth = 3; g.shadowColor = css; g.shadowBlur = 8;
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(ex, ey); g.stroke();
    g.shadowBlur = 0;
    if (f < 0.999) { g.fillStyle = css; g.beginPath(); g.arc(ex, ey, 4, 0, 7); g.fill(); }
    g.fillStyle = "#94a3b8"; g.font = "600 10px JetBrains Mono, monospace"; g.textAlign = "center";
    g.fillText(d >= alc - 0.01 ? "—" : d.toFixed(1), cx + Math.cos(a) * (R + 10) * 0.98, cy + Math.sin(a) * (R + 10) * 0.98 + 3);
  });
  g.fillStyle = "#e10600"; g.beginPath(); g.roundRect(cx - 6, cy - 9, 12, 20, 3); g.fill();
}

function dibujarGrafica(i) {
  const [, g, W, H] = lienzo2D($("grafica"));
  g.clearRect(0, 0, W, H);
  const f = ep.frames, n = f.length;
  let lo = 0, hi = 0;
  for (const fr of f) { lo = Math.min(lo, fr.R); hi = Math.max(hi, fr.R); }
  const y = (v) => H - 6 - (v - lo) / (hi - lo || 1) * (H - 12);
  const x = (k) => k / (n - 1) * W;
  g.strokeStyle = "rgba(148,163,184,.25)"; g.setLineDash([3, 4]);
  g.beginPath(); g.moveTo(0, y(0)); g.lineTo(W, y(0)); g.stroke(); g.setLineDash([]);
  g.strokeStyle = "rgba(148,163,184,.3)"; g.lineWidth = 1.5;
  g.beginPath(); f.forEach((fr, k) => (k ? g.lineTo(x(k), y(fr.R)) : g.moveTo(x(k), y(fr.R)))); g.stroke();
  const grad = g.createLinearGradient(0, 0, W, 0);
  grad.addColorStop(0, "#e10600"); grad.addColorStop(1, "#ffd23f");
  g.strokeStyle = grad; g.lineWidth = 2.5;
  g.beginPath(); for (let k = 0; k <= i; k++) (k ? g.lineTo(x(k), y(f[k].R)) : g.moveTo(x(k), y(f[k].R))); g.stroke();
  g.fillStyle = "#fff"; g.beginPath(); g.arc(x(i), y(f[i].R), 3.5, 0, 7); g.fill();
}


function dibujarMinimapa(est) {
  const [, g, W, H] = lienzo2D($("minimapa"));
  const [MX, MY] = pista.mapa, k = Math.min(W / (2 * MX), H / (2 * MY));
  const X = (x) => W / 2 + x * k, Y = (y) => H / 2 - y * k;
  if (!fondoMini) {
    const c = document.createElement("canvas"); c.width = W * 2; c.height = H * 2;
    const b = c.getContext("2d");
    b.scale(2, 2);
    b.lineJoin = "round";
    const camino = () => { b.beginPath(); pista.centro.forEach(([, x, y], i) => (i ? b.lineTo(X(x), Y(y)) : b.moveTo(X(x), Y(y)))); b.closePath(); };
    b.strokeStyle = "#000"; b.lineWidth = 7; camino(); b.stroke();
    b.strokeStyle = "#e8eaee"; b.lineWidth = 3.5; camino(); b.stroke();
    fondoMini = c;
  }
  g.clearRect(0, 0, W, H);
  g.drawImage(fondoMini, 0, 0, W, H);
  pista.puertas.forEach((p) => {
    const id = p.id, cp = est.b.cp;
    g.strokeStyle = id < cp ? "#2ee59d" : id === cp ? "#ffd23f" : "#6d7686";
    g.lineWidth = id === cp ? 5 : 4;
    const nx = -Math.sin(p.h) * 6 / k, ny = Math.cos(p.h) * 6 / k;
    g.beginPath(); g.moveTo(X(p.x + nx), Y(p.y + ny)); g.lineTo(X(p.x - nx), Y(p.y - ny)); g.stroke();
  });
  g.strokeStyle = "#e10600"; g.lineWidth = 3;
  g.beginPath();
  for (let i = 0; i <= est.i; i++) { const f = ep.frames[i]; i ? g.lineTo(X(f.x), Y(f.y)) : g.moveTo(X(f.x), Y(f.y)); }
  g.stroke();
  g.save();
  g.translate(X(est.x), Y(est.y)); g.rotate(-est.psi);
  g.fillStyle = "#ffd23f"; g.strokeStyle = "#000"; g.lineWidth = 1.5;
  g.beginPath(); g.moveTo(9, 0); g.lineTo(-6, 5.5); g.lineTo(-3, 0); g.lineTo(-6, -5.5); g.closePath(); g.stroke(); g.fill();
  g.restore();
}

// ------------------------------------------------------------------ episodio
// Parámetros del experimento (los rangos vienen de la ficha, vía /api/pista)
const PARAMS = [
  { k: "ancho", nombre: "Ancho de pista", u: "m", dec: 1 },
  { k: "mu", nombre: "Adherencia μ", u: "", dec: 2 },
  { k: "a_max", nombre: "Aceleración máx.", u: "m/s²", dec: 1 },
  { k: "r_max", nombre: "Alcance sensores", u: "m", dec: 0 },
];
const valorParam = (k) => parseFloat($(`p-${k}`).value);
function ponerParam(k, v) {
  const el = $(`p-${k}`), rg = pista.rangos[k];
  el.value = clamp(v, rg.min, rg.max);
  const p = PARAMS.find((x) => x.k === k);
  $(`o-${k}`).textContent = `${(+el.value).toFixed(p.dec)} ${p.u}`;
  el.closest(".param").classList.toggle("cambiado", Math.abs(+el.value - rg.base) > 1e-9);
  if (k === "mu") document.querySelectorAll("#sel-piso button").forEach((b) => b.classList.toggle("activo", Math.abs(parseFloat(b.dataset.mu) - el.value) < 1e-9));
}
function construirParametros() {
  $("parametros").innerHTML = PARAMS.map(({ k, nombre }) => {
    const r = pista.rangos[k];
    return `<label class="param"><span>${nombre}</span><output id="o-${k}"></output>
      <input id="p-${k}" type="range" min="${r.min}" max="${r.max}" step="${r.paso}" value="${r.base}">
      <small>ficha: ${r.min}–${r.max} · base ${r.base}</small></label>`;
  }).join("");
  for (const { k } of PARAMS) {
    $(`p-${k}`).oninput = (e) => ponerParam(k, +e.target.value);
    ponerParam(k, params.has(k) ? parseFloat(params.get(k)) : pista.rangos[k].base);
  }
}
function sortear() {
  for (const { k } of PARAMS) {
    const r = pista.rangos[k], pasos = Math.round((r.max - r.min) / r.paso);
    ponerParam(k, r.min + Math.floor(Math.random() * (pasos + 1)) * r.paso);
  }
  $("inp-semilla").value = Math.floor(Math.random() * 10000);
}

// Registro de experimentos de la sesión (se guardan los episodios para repetirlos)
const experimentos = [];
const NOMBRE_FIN = { exito: "Vuelta completa", choque: "Choque", salida: "Salida de pista", estancado: "Estancado", tiempo: "Sin tiempo" };
function pintarExperimentos() {
  $("n-exp").textContent = experimentos.length;
  if (!experimentos.length) return;
  const ok = experimentos.filter((e) => e.resultado === "exito");
  const mejor = ok.length ? Math.min(...ok.map((e) => e.tiempo)).toFixed(1) + " s" : "—";
  const resumen = `<div class="resumen-exp">
    <div><small>Corridas</small><strong>${experimentos.length}</strong></div>
    <div><small>Éxito</small><strong>${Math.round(100 * ok.length / experimentos.length)}%</strong></div>
    <div><small>Mejor vuelta</small><strong>${mejor}</strong></div></div>`;
  const filas = experimentos.slice().reverse().map((e) => {
    const p = e.params, bien = e.resultado === "exito";
    return `<button class="exp ${ep && !ep.vivo && e.id === ep.id ? "actual" : ""}" data-id="${e.id}">
      <span class="num">#${e.id}</span>
      <span class="res ${bien ? "ok" : "mal"}">${NOMBRE_FIN[e.resultado]}</span>
      <span class="met">${e.tiempo.toFixed(1)} s · ${e.recompensa >= 0 ? "+" : ""}${e.recompensa.toFixed(1)}</span>
      <span class="det">${e.piloto} · μ ${p.mu.toFixed(2)} · ${p.ancho} m · a ${p.a_max} · sensor ${p.r_max} m · semilla ${e.semilla}</span>
    </button>`;
  }).join("");
  $("lista-exp").innerHTML = resumen + filas;
  $("lista-exp").querySelectorAll(".exp").forEach((b) => (b.onclick = () => verExperimento(+b.dataset.id)));
}
function verExperimento(id) {
  const e = experimentos.find((x) => x.id === id);
  if (!e) return;
  $("sel-piloto").value = e.piloto;
  $("inp-semilla").value = e.semilla;
  for (const { k } of PARAMS) ponerParam(k, e.params[k]);
  mostrarEpisodio(e.episodio);
}

async function cargarEpisodio() {
  const piloto = $("sel-piloto").value, semilla = parseInt($("inp-semilla").value || "0", 10);
  $("cargando-txt").textContent = `Simulando en Python (${piloto})…`;
  $("cargando").classList.remove("oculto");
  $("resultado").classList.add("oculto");
  const q = new URLSearchParams({ piloto, semilla, pista: pista.pista ?? "monaco" });
  for (const { k } of PARAMS) q.set(k, valorParam(k));
  const fallo = (texto) => {
    $("cargando-txt").textContent = texto;
    setTimeout(() => $("cargando").classList.add("oculto"), 4000);  // sigue visible la vuelta anterior
  };
  let r;
  try {
    r = await fetch(`${API}/api/episodio?${q}`);
  } catch {
    fallo("Error: no hay conexión con la API de simulación");
    return;
  }
  if (!r.ok) {  // un error del servicio se muestra como error, nunca como un episodio
    const e = await r.json().catch(() => ({}));
    fallo(`Error del servicio: ${e.detail ?? r.status}`);
    return;
  }
  const nuevo = await r.json();
  experimentos.push({ ...nuevo, episodio: nuevo });
  // Si mientras tanto se entró al modo en vivo y ya se ve un episodio del entrenamiento,
  // no se reemplaza: solo queda en el registro.
  if (modoVivo && ep && ep.vivo) { pintarExperimentos(); $("cargando").classList.add("oculto"); return; }
  mostrarEpisodio(nuevo);
}

function mostrarEpisodio(nuevo) {
  ep = nuevo;
  // Los episodios del entrenamiento en vivo traen el ancho como `track_width` (nombre
  // del ambiente). Sin esto la pista y el fondo del minimapa se construían con ancho
  // indefinido (NaN) y el minimapa quedaba casi vacío.
  ep.params.ancho = ep.params.ancho ?? ep.params.track_width ?? pista.ancho;
  mu = ep.params.mu ?? pista.rangos.mu.base;
  if (ep.params.ancho !== anchoConstruido) construirPista(ep.params.ancho);
  $("t-experimento").textContent = ep.vivo ? `ENTRENAMIENTO · EPISODIO #${ep.id}` : `EXPERIMENTO #${ep.id}`;
  const modo = ep.vivo ? "entrenamiento" : ep.modo ?? "evaluacion";
  $("insignia-modo").textContent = `${modo} · ${ep.modelo ?? ep.piloto ?? "piloto"}`;
  $("insignia-modo").dataset.modo = modo;
  $("insignia-modo").title = ep.ambiente_del_modelo
    ? `Ambiente del modelo: ${ep.ambiente_del_modelo} · servido: ${ep.ambiente_servido}${ep.adaptador ? " (con adaptador validado)" : ""}`
    : "";
  pintarExperimentos();
  aplicarClima();
  construirEstela();
  tiempo = parseFloat(params.get("t") || "0");
  params.delete("t");
  ultimoCP = 1;
  reproduciendo = params.get("pausa") !== "1";
  $("btn-play").textContent = reproduciendo ? "❚❚" : "▶";
  if (listo) $("cargando").classList.add("oculto");
  const est = estado();
  cam.position.copy(P(est.x, est.y)).add(new THREE.Vector3(-30, 25, 30));
  mirarSuave.copy(P(est.x, est.y));
}

function mostrarResultado() {
  const ok = ep.resultado === "exito", last = ep.frames[ep.frames.length - 1];
  $("resultado").dataset.fin = ok ? "ok" : "mal";
  $("r-titulo").textContent = { exito: "VUELTA COMPLETA", choque: "CHOQUE", salida: "SALIDA DE PISTA", estancado: "ESTANCADO", tiempo: "TIEMPO AGOTADO" }[ep.resultado];
  $("r-titulo").style.color = ok ? "#fff" : "#ff4d45";
  $("r-tiempo").textContent = `${ep.tiempo.toFixed(1)} s`;
  $("r-recompensa").textContent = `${ep.recompensa >= 0 ? "+" : ""}${ep.recompensa.toFixed(1)}`;
  $("r-recompensa").style.color = ep.recompensa >= 0 ? "#2ee59d" : "#ff4d45";
  $("r-progreso").textContent = `${Math.round(100 * last.s / pista.largo)}%`;
  $("r-salidas").textContent = ep.salidas;
  $("resultado").classList.remove("oculto");
}

// ------------------------------------------------------------------ rendimiento
// Mide los FPS y ajusta la resolución sola: si van lentos la baja, si sobran la sube.
const fpsEl = document.createElement("div");
fpsEl.id = "fps";
$("acciones").prepend(fpsEl);
let fpsT0 = performance.now(), fpsCuadros = 0, fpsVentana = 0;
let malos = 0, buenos = 0, espera = 0, techoRes = 9, techoHasta = 0;   // techoRes: nivel que ya se probó y fue lento
// Se llama ANTES de dibujar: cambiar el tamaño del lienzo lo borra, y si se hace después
// de dibujar el navegador muestra ese cuadro vacío (el parpadeo negro).
// Usa el reloj real (el dt del bucle está topado en 0.1 s y no mostraría menos de 10 FPS).
function medirFps() {
  fpsCuadros++;
  const ahora = performance.now(), seg = (ahora - fpsT0) / 1000;
  if (seg < 1) return;
  const fps = fpsCuadros / seg;
  fpsT0 = ahora; fpsCuadros = 0; fpsVentana++;
  if (ahora > techoHasta) techoRes = 9;          // el techo vence al minuto (un bache pasajero no lo deja para siempre)
  fpsEl.textContent = `${fps.toFixed(0)} FPS · ${Math.round(resolucion * 100)}% · ${Q.nombre}`;
  fpsEl.className = fps < 30 ? "lento" : "";
  if (fpsVentana <= 3 || document.hidden) return;   // carga inicial o pestaña oculta
  // Margen: hacen falta 3 s seguidos lentos para bajar y 5 s seguidos sobrados para subir,
  // con una pausa de 8 s después de cada cambio. Si al subir se pone lento, ese nivel
  // queda como techo: así no sube y baja sin parar (cada cambio da un tirón).
  malos = fps < 30 ? malos + 1 : 0;
  buenos = fps > 55 ? buenos + 1 : 0;
  if (espera > 0) { espera--; return; }
  const tope = Math.min(devicePixelRatio, Q.px, techoRes), antes = resolucion;
  if (malos >= 3 && resolucion > 0.7) {
    techoRes = resolucion - 0.01; techoHasta = ahora + 60000;
    resolucion = Math.max(0.7, Math.round((resolucion - 0.1) * 10) / 10);
  } else if (buenos >= 5 && resolucion + 0.1 <= tope + 1e-6) {
    resolucion = Math.round((resolucion + 0.1) * 10) / 10;
  }
  if (resolucion !== antes) {
    malos = buenos = 0; espera = 8;
    renderer.setPixelRatio(resolucion);
    composer.setPixelRatio(resolucion);
    composer.setSize(innerWidth, innerHeight);
    ajustarFxaa();
  }
}

// ------------------------------------------------------------------ bucle
const reloj = new THREE.Clock();
let terminado = false;
function animar() {
  requestAnimationFrame(animar);
  const dt = Math.min(reloj.getDelta(), 0.1);
  if (!ep) return;
  const dur = (ep.frames.length - 1) * pista.dt;
  if (reproduciendo && listo) {
    tiempo += dt * velocidad;
    if (tiempo >= dur) {
      tiempo = dur;
      reproduciendo = false;
      $("btn-play").textContent = "▶";
      if (!terminado) { terminado = true; if (ep.vivo) mostrarFinVivo(); else setTimeout(mostrarResultado, 700); }
    }
  }
  if (tiempo < dur) terminado = false;
  const est = estado();

  carro.position.copy(P(est.x, est.y));
  carro.rotation.y = est.psi;
  const delta = est.accion[1] * pista.delta_max;
  for (const r of ruedas) {
    if (r.delantera) r.pivote.rotation.y = delta;
    r.giro.rotation.z -= est.v * dt * velocidad * (reproduciendo ? 1 : 0) / 0.36;
  }
  carro.rotation.z = clamp(-est.accion[0] * 0.02, -0.02, 0.02);         // cabeceo al acelerar/frenar
  carro.rotation.x = clamp(est.accion[1] * est.v * 0.002, -0.05, 0.05);  // inclinación en curva
  luzFreno.emissiveIntensity = est.accion[0] < -0.05 ? 4 : 0.4;

  // Humo de llantas: al derrapar, al pisar la zona de escape o al arrancar fuerte
  if (reproduciendo && humo) {
    let fuerte = est.b.derrape ? 1 : est.b.fuera > 0 ? 0.8 : est.accion[0] > 0.8 && est.v < 7 ? 0.35 : 0;
    if (mu < 0.75 && est.v > 6) fuerte = Math.max(fuerte, (est.v / 25) * 0.55);   // rocío de agua con lluvia
    if (fuerte > 0) {
      const back = -pista.carro.ejes / 2, W = pista.carro.ancho / 2;
      for (const lado of [W, -W]) {
        const p = rueda({ x: est.x, y: est.y, psi: est.psi }, back, lado);
        humo.emitir(P(p.x, p.y), fuerte * Math.min(1, dt * velocidad * 60));
      }
    }
  }
  if (humo) humo.actualizar(dt * Math.max(velocidad, 1));
  if (escenario) escenario.actualizar(dt, performance.now() / 1000);

  // Rayos desde el carro (distancias reales de la observación)
  pista.rayos.angulos.forEach((ang, k) => {
    const d = est.b.rayos[k], a = est.psi + ang;
    const ini = P(est.x, est.y, 0.7), fin = P(est.x + Math.cos(a) * d, est.y + Math.sin(a) * d, 0.35);
    const { linea, punta, anillo } = rayos[k];
    linea.geometry.attributes.position.setXYZ(0, ini.x, ini.y, ini.z);
    linea.geometry.attributes.position.setXYZ(1, fin.x, fin.y, fin.z);
    linea.geometry.attributes.position.needsUpdate = true;
    const c = colorDistancia(d);
    linea.material.color.copy(c);
    linea.material.opacity = d >= alcance() - 0.01 ? 0.25 : 0.9;
    punta.material.color.copy(c);
    anillo.material.color.copy(c);
    const hay = d < alcance() - 0.01;
    punta.visible = anillo.visible = hay;
    punta.position.copy(fin);
    anillo.position.set(fin.x, 0.06, fin.z);
    anillo.scale.setScalar(1 + 0.25 * Math.sin(performance.now() / 150 + k));
  });

  // Puertas: siguiente en amarillo, pasadas en verde
  for (const g of puertas) {
    const id = g.userData.id, cp = est.b.cp;
    const color = id < cp ? 0x22c55e : id === cp ? 0xfacc15 : 0x38bdf8;
    g.userData.mat.color.setHex(color);
    g.userData.mat.emissive.setHex(color);
    g.userData.mat.emissiveIntensity = id === cp ? 0.9 + 0.5 * Math.sin(performance.now() / 200) : 0.35;
    if (g.userData.franja) g.userData.franja.material.color.setHex(color);
  }

  estela.geometry.setDrawRange(0, est.i * 6);
  marcas.geometry.setDrawRange(0, marcasPorFrame[est.i] || 0);

  if (lluvia.visible) {
    const p = lluvia.geometry.attributes.position, arr = p.array, caida = 30 * dt;
    for (let i = 0; i < arr.length; i += 6) {
      let y = arr[i + 1] - caida;
      if (y < 0) y += 40;
      arr[i + 1] = y;
      arr[i + 4] = y + GOTA;
    }
    p.needsUpdate = true;
    lluvia.position.set(cam.position.x * 0.6, 0, cam.position.z * 0.6);
  }

  // Sombras nítidas: la cámara de sombras del sol sigue al carro (cuadro de 120 m)
  {
    const dir = sol.userData.direccion;
    if (dir) {
      const centro = P(est.x, est.y);
      sol.position.copy(centro).addScaledVector(dir, 200);
      sol.target.position.copy(centro);
      sol.target.updateMatrixWorld();
    }
  }
  actualizarCamara(est, dt);
  hudAcum += dt;
  if (!SIN.has("hud") && (hudAcum >= 0.05 || !reproduciendo)) { hudAcum = 0; actualizarHUD(est); }
  cuadro++;
  if (Q.cadaSombra > 1 && cuadro % Q.cadaSombra === 0) renderer.shadowMap.needsUpdate = true;
  gradacion.uniforms.tiempo.value = (cuadro % 997) * 0.37;
  if (listo) medirFps();   // antes de dibujar (ver medirFps); el arranque no cuenta como lentitud
  if (SIN.has("post")) renderer.render(scene, cam); else composer.render();
}

// ------------------------------------------------------------------ entrenamiento en vivo
// El entrenamiento (Python) guarda cada episodio terminado en runs/vivo/. Aquí se
// consulta cada 1.5 s y se reproduce el más reciente: se ve al modelo mejorar.
let modoVivo = false, vivoTimer = null, vivoUltimo = 0, velocidadPrevia = 1, finVivoTimer = null;
const NOMBRE_AGENTE = { ppo: "PPO · red neuronal", qlearning: "Q-learning · tabla" };
const nombreAgente = (a) => NOMBRE_AGENTE[a] || String(a || "agente").toUpperCase();

// Aviso breve en la telemetría con el resultado del episodio en vivo que se acaba de ver
// (reemplaza a la tarjeta de resultado, que en vivo taparía la escena cada episodio)
function mostrarFinVivo() {
  if (!modoVivo || !ep || !ep.vivo) return;
  const ok = ep.resultado === "exito", last = ep.frames[ep.frames.length - 1];
  const prog = ep.progreso ?? 100 * last.s / pista.largo;
  const R = ep.recompensa ?? last.R;
  $("fin-vivo").className = `fin-vivo ${ok ? "ok" : "mal"}`;
  $("fin-vivo-icono").textContent = { exito: "🏁", choque: "💥", salida: "🌀", estancado: "⏸", tiempo: "⏱" }[ep.resultado] || "■";
  $("fin-vivo-titulo").textContent = `Episodio #${ep.id} · ${{ exito: "Vuelta completa", choque: "Choque", salida: "Salida de pista", estancado: "Estancado", tiempo: "Sin tiempo" }[ep.resultado] || ep.resultado}`;
  $("fin-vivo-datos").textContent = `${(ep.tiempo ?? last.t).toFixed(1)} s · ${R >= 0 ? "+" : ""}${R.toFixed(1)} pts · ${Math.round(prog)}% de la vuelta`;
  clearTimeout(finVivoTimer);
  finVivoTimer = setTimeout(ocultarFinVivo, 6000);
}
function ocultarFinVivo() {
  clearTimeout(finVivoTimer);
  $("fin-vivo").classList.add("oculto");
}

// Panel izquierdo en modo en vivo: quién maneja y controles deshabilitados
function pintarManejando(c) {
  if (!c) {
    $("manejando-agente").textContent = "Esperando entrenamiento…";
    $("manejando-detalle").textContent = "aún no hay episodios";
    return;
  }
  const ult = c.episodios[c.episodios.length - 1];
  $("manejando-agente").textContent = nombreAgente(c.agente);
  $("manejando-detalle").textContent = `(entrenando) · episodio ${ult.episodio}`;
}

async function sondearVivo() {
  try {
    const c = await (await fetch(`${API}/api/vivo/curva`)).json();
    if (!modoVivo) return;  // se salió del modo en vivo mientras se esperaba la respuesta
    if (!c.episodios || !c.episodios.length) { estadoVivo(null); return; }
    estadoVivo(c);
    dibujarCurvas(c.episodios);
    const ult = c.episodios[c.episodios.length - 1];
    const fin = ep ? (ep.frames.length - 1) * pista.dt : 0;
    const libre = !ep || !ep.vivo || !reproduciendo || tiempo >= fin - 0.05;
    if (ult.episodio > vivoUltimo && libre) {
      const e = await (await fetch(`${API}/api/vivo/episodio`)).json();
      if (e.frames && modoVivo) { vivoUltimo = e.id; e.vivo = true; mostrarEpisodio(e); }
    }
  } catch (err) { /* el entrenamiento puede estar escribiendo; se reintenta */ }
}

function estadoVivo(c) {
  const el = $("apr-estado");
  pintarManejando(c);
  if (!c) {
    el.className = "apr-estado";
    $("insignia-txt").textContent = "EN VIVO · esperando entrenamiento…";
    return;
  }
  const eps = c.episodios, ult = eps[eps.length - 1], rec = eps.slice(-50);
  const vueltas = Math.round(100 * rec.filter((e) => e.resultado === "exito").length / rec.length);
  const mejor = Math.max(...eps.map((e) => e.progreso));
  const pasos = ult.pasos_totales >= 1e6 ? (ult.pasos_totales / 1e6).toFixed(2) + " M" : Math.round(ult.pasos_totales / 1e3) + " k";
  const min = (c.segundos / 60).toFixed(1);
  el.className = "apr-estado activo";
  el.textContent = `Entrenando ${c.agente.toUpperCase()} · ${min} min · ${pasos} pasos de simulación`;
  $("insignia-txt").textContent = `EN VIVO · ${c.agente.toUpperCase()} · episodio ${ult.episodio} · ${pasos} pasos`;
  $("apr-resumen").innerHTML = `
    <div><small>Episodios</small><strong>${ult.episodio}</strong></div>
    <div><small>Vueltas (últ. 50)</small><strong>${vueltas}%</strong></div>
    <div><small>Mejor progreso</small><strong>${mejor.toFixed(0)}%</strong></div>`;
}

function dibujarCurvas(eps) {
  const dib = (id, valor, lo, hi, color) => {
    const [, g, W, H] = lienzo2D($(id)), n = eps.length;
    g.clearRect(0, 0, W, H);
    const x = (i) => 4 + (i / Math.max(n - 1, 1)) * (W - 8), y = (v) => H - 6 - (clamp(v, lo, hi) - lo) / (hi - lo || 1) * (H - 12);
    g.strokeStyle = "rgba(148,163,184,.15)";
    for (const f of [0.25, 0.5, 0.75]) { g.beginPath(); g.moveTo(0, H * f); g.lineTo(W, H * f); g.stroke(); }
    eps.forEach((e, i) => {
      g.fillStyle = e.resultado === "exito" ? "rgba(46,229,157,.8)" : "rgba(152,161,176,.35)";
      g.fillRect(x(i) - 1, y(valor(e)) - 1, 2.2, 2.2);
    });
    const k = Math.max(5, Math.round(n / 25));  // media móvil
    g.strokeStyle = color; g.lineWidth = 2.5; g.beginPath();
    for (let i = 0; i < n; i++) {
      const v = eps.slice(Math.max(0, i - k), i + 1).reduce((a, e) => a + valor(e), 0) / Math.min(i + 1, k + 1);
      i ? g.lineTo(x(i), y(v)) : g.moveTo(x(i), y(v));
    }
    g.stroke();
  };
  dib("curva-progreso", (e) => e.progreso, 0, 100, "#ffd23f");
  const rs = eps.map((e) => e.recompensa);
  dib("curva-recompensa", (e) => e.recompensa, Math.min(...rs), Math.max(...rs), "#e10600");
}

function alternarVivo() {
  modoVivo = !modoVivo;
  $("btn-vivo").classList.toggle("activo", modoVivo);
  $("btn-vivo").textContent = modoVivo ? "■ Salir de en vivo" : "● En vivo";
  $("insignia-vivo").classList.toggle("oculto", !modoVivo);
  // Piloto, piso, parámetros y semilla no aplican mientras se ve el entrenamiento
  document.body.classList.toggle("en-vivo", modoVivo);
  $("controles-experimento").disabled = modoVivo;
  $("btn-correr").disabled = modoVivo;
  $("manejando").classList.toggle("oculto", !modoVivo);
  clearInterval(vivoTimer);
  ocultarFinVivo();
  if (modoVivo) {
    pintarManejando(null);
    velocidadPrevia = velocidad;
    document.querySelector('.pestanas button[data-tab="apr"]').click();
    $("resultado").classList.add("oculto");
    document.querySelector('#sel-vel button[data-v="2"]').click();
    sondearVivo();
    vivoTimer = setInterval(sondearVivo, 1500);
  } else {
    // Volver a la normalidad: velocidad previa y último experimento propio (si lo hay)
    document.querySelector(`#sel-vel button[data-v="${velocidadPrevia}"]`)?.click();
    document.querySelector('.pestanas button[data-tab="tel"]').click();
    vivoUltimo = 0;
    const ultimo = experimentos[experimentos.length - 1];
    if (ep && ep.vivo && ultimo) verExperimento(ultimo.id);
  }
}

// ------------------------------------------------------------------ eventos
function conectar() {
  const sel = $("sel-piloto");
  for (const [k, desc] of Object.entries(pista.pilotos)) sel.insertAdjacentHTML("beforeend", `<option value="${k}" title="${desc}">${k} — ${desc}</option>`);
  sel.value = params.get("piloto") || pista.recomendado || "experto";
  $("inp-semilla").value = params.get("semilla") || "0";

  // Selector de pista: solo si la API dice cuáles hay (el replay sin API trae solo Mónaco)
  const selPista = $("sel-pista");
  if (pista.pistas?.length > 1) {
    for (const p of pista.pistas) {
      selPista.insertAdjacentHTML("beforeend", `<option value="${p.nombre}" title="${p.descripcion}">${p.titulo} · ${p.largo} m</option>`);
    }
    selPista.value = pista.pista;
    selPista.onchange = () => {
      if (selPista.value === "monaco") params.delete("pista"); else params.set("pista", selPista.value);
      for (const k of ["t", "pausa"]) params.delete(k);
      location.search = params.toString();   // recarga: el escenario se arma con la pista nueva
    };
  } else {
    $("campo-pista").classList.add("oculto");
  }

  construirParametros();
  $("btn-correr").onclick = cargarEpisodio;
  $("btn-azar").onclick = () => { sortear(); cargarEpisodio(); };
  document.querySelectorAll("#sel-piso button").forEach((b) => (b.onclick = () => { ponerParam("mu", parseFloat(b.dataset.mu)); cargarEpisodio(); }));
  document.querySelectorAll(".pestanas button").forEach((b) => (b.onclick = () => {
    document.querySelectorAll(".pestanas button").forEach((x) => x.classList.toggle("activo", x === b));
    for (const t of ["tel", "exp", "apr"]) $(`tab-${t}`).classList.toggle("oculto", b.dataset.tab !== t);
  }));
  $("btn-vivo").onclick = alternarVivo;
  if (params.get("vivo") === "1") setTimeout(alternarVivo, 0);
  document.querySelectorAll("#camaras button[data-cam]").forEach((b) => (b.onclick = () => ponerCamara(b.dataset.cam)));
  const paneles = () => document.body.classList.toggle("limpio");
  $("btn-paneles").onclick = paneles;
  $("btn-plegar").onclick = () => {
    const plegado = document.body.classList.toggle("plegado");
    $("btn-plegar").setAttribute("aria-expanded", String(!plegado));
  };
  const selCalidad = $("sel-calidad");
  selCalidad.value = eleccion;
  selCalidad.title = `Tarjeta gráfica: ${GPU || "desconocida"} · en uso: ${Q.nombre}`;
  selCalidad.onchange = () => {
    try { localStorage.setItem("rally-calidad", selCalidad.value); } catch (e) { /* sin almacenamiento */ }
    const u = new URL(location.href); u.searchParams.delete("calidad"); location.href = u.toString();
  };
  if (params.get("limpio") === "1") document.body.classList.add("limpio");
  // Indicador de carga de los recursos pesados (cielo, carro, texturas, faroles)
  const indicador = document.createElement("div");
  indicador.id = "cargas";
  document.body.appendChild(indicador);
  const pintarCargas = () => {
    const lista = [...cargas.entries()];
    const ok = lista.filter(([, e]) => e === "ok").length, mal = lista.filter(([, e]) => e === "error");
    if (lista.length && ok === lista.length) { indicador.remove(); clearInterval(timerCargas); return; }
    indicador.innerHTML = `Cargando escenario ${ok}/${lista.length}` +
      lista.filter(([, e]) => e !== "ok").map(([n, e]) => `<div class="${e}">${e === "error" ? "✖" : "…"} ${n}</div>`).join("");
    if (mal.length && ok + mal.length === lista.length) clearInterval(timerCargas);
  };
  const timerCargas = setInterval(pintarCargas, 500);
  if (params.get("tab") === "exp") setTimeout(() => document.querySelector('.pestanas button[data-tab="exp"]').click(), 0);
  document.querySelectorAll("#sel-vel button").forEach((b) => (b.onclick = () => {
    velocidad = parseFloat(b.dataset.v);
    document.querySelectorAll("#sel-vel button").forEach((x) => x.classList.toggle("activo", x === b));
  }));
  const playPausa = () => {
    if (!reproduciendo && tiempo >= (ep.frames.length - 1) * pista.dt) tiempo = 0;
    reproduciendo = !reproduciendo;
    $("btn-play").textContent = reproduciendo ? "❚❚" : "▶";
    $("resultado").classList.add("oculto");
  };
  $("btn-play").onclick = playPausa;
  $("btn-reiniciar").onclick = () => { tiempo = 0; reproduciendo = true; $("btn-play").textContent = "❚❚"; $("resultado").classList.add("oculto"); };
  $("barra").oninput = (e) => { tiempo = e.target.value * (ep.frames.length - 1) * pista.dt; };
  $("r-repetir").onclick = () => $("btn-reiniciar").onclick();
  $("r-cerrar").onclick = () => $("resultado").classList.add("oculto");
  $("r-cambiar").onclick = () => { ponerParam("mu", mu < 0.75 ? 0.9 : 0.5); cargarEpisodio(); };

  addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("resultado").classList.add("oculto");
    // Los deslizadores no escriben: si los atajos los ignoran, el teclado queda muerto tras usarlos
    if (e.target.type !== "range" && (e.target.tagName === "INPUT" || e.target.tagName === "SELECT")) return;
    const cams =["persecucion", "tv", "aerea", "cabina", "libre", "vitrina"];
    if (e.key >= "1" && e.key <= "6") ponerCamara(cams[+e.key - 1]);
    if (e.code === "Space") { e.preventDefault(); playPausa(); }
    if (e.key === "r" || e.key === "R") $("btn-reiniciar").onclick();
    if (e.key === "h" || e.key === "H") paneles();
    if (e.key === "ArrowRight") tiempo = Math.min(tiempo + 2, (ep.frames.length - 1) * pista.dt);
    if (e.key === "ArrowLeft") tiempo = Math.max(tiempo - 2, 0);
  });
  addEventListener("resize", () => {
    cam.aspect = innerWidth / innerHeight;
    cam.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
    composer.setSize(innerWidth, innerHeight);
    ajustarFxaa();
  });
}

// Mantiene la pantalla de carga hasta que llegan texturas, cielo y carro, y deja correr unos
// cuadros detrás de ella: ahí se compilan los shaders, que si no traban los primeros segundos.
// Con internet muy lenta no se espera para siempre: lo que falte aparece después con su indicador.
async function prepararEscena(limite = 15000) {
  const t0 = performance.now();
  let estables = 0;
  while (estables < 3 && performance.now() - t0 < limite) {
    await new Promise((r) => setTimeout(r, 100));
    const lista = [...cargas.values()], ok = lista.filter((e) => e !== "cargando").length;
    $("cargando-txt").textContent = `Preparando escenario ${ok}/${lista.length}…`;
    estables = lista.length && ok === lista.length ? estables + 1 : 0;
  }
  for (let i = 0; i < 4; i++) await new Promise((r) => requestAnimationFrame(r));
  listo = true;
  fpsT0 = performance.now(); fpsCuadros = 0;
  reloj.getDelta();
  $("cargando").classList.add("oculto");
}

// ------------------------------------------------------------------ inicio
// La pista se elige con ?pista=: el escenario se construye una vez a partir de su geometría.
// Si la pedida no está disponible (reservada, desconocida o sin API), se carga Mónaco y se avisa.
let avisoPista = "";
{
  let r = await fetch(`${API}/api/pista?pista=${encodeURIComponent(PISTA_PEDIDA)}`);
  if (!r.ok && PISTA_PEDIDA !== "monaco") {
    const e = await r.json().catch(() => ({}));
    avisoPista = `${e.detail ?? `La pista ${PISTA_PEDIDA} no está disponible`}. Se muestra Mónaco.`;
    params.delete("pista");
    history.replaceState(null, "", `${location.pathname}${params.toString() ? `?${params}` : ""}`);
    r = await fetch(`${API}/api/pista`);
  }
  pista = await r.json();
}
$("subtitulo-pista").textContent = `${pista.titulo ?? "Mónaco"} · AutonomousRally-v0`;
{
  const [MX, MY] = pista.mapa;
  // Cámara de sombras de 120 m que sigue al carro (más detalle que cubrir todo el mapa)
  Object.assign(sol.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 450 });
  sol.shadow.camera.updateProjectionMatrix();
  scene.add(sol.target);
  void MX; void MY;
}
prepararCamsTV();
construirMundo();
construirPista(pista.ancho);
construirCarro();
construirRayos();
construirLluvia();
prepararHUD();
conectar();
ponerCamara(camara);
await cargarEpisodio();
animar();
await prepararEscena();
if (avisoPista) aviso(avisoPista, "cesped", 8000);
