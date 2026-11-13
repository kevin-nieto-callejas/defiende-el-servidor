// Moto de velocidad tipo MotoGP con su piloto, hecha con geometría de three.js (sin modelos
// descargados). Diseño propio con la decoración del proyecto: azul, dorado y el número 24.
// Las medidas son las del simulador (rally/moto.py): largo 2.1 m, ancho 0.8 m con el piloto,
// 1.45 m entre ejes. El origen está en el suelo, en medio de los dos ejes: el visor inclina el
// grupo entero sobre la línea de contacto de las llantas.

import * as THREE from "three";

const R_LLANTA = 0.31;

function texturaCarenado() {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 384;
  const g = c.getContext("2d");
  const fondo = g.createLinearGradient(0, 0, 1024, 0);
  fondo.addColorStop(0, "#0f172a"); fondo.addColorStop(0.35, "#1d4ed8"); fondo.addColorStop(1, "#1e3a8a");
  g.fillStyle = fondo; g.fillRect(0, 0, 1024, 384);
  // Franjas doradas en diagonal (velocidad)
  g.fillStyle = "#d4a017";
  g.beginPath(); g.moveTo(0, 300); g.lineTo(1024, 150); g.lineTo(1024, 210); g.lineTo(0, 360); g.closePath(); g.fill();
  g.fillStyle = "#facc15";
  g.beginPath(); g.moveTo(0, 368); g.lineTo(1024, 220); g.lineTo(1024, 232); g.lineTo(0, 380); g.closePath(); g.fill();
  // Número (placa blanca redonda) y nombre
  g.fillStyle = "#f8fafc"; g.beginPath(); g.ellipse(640, 150, 92, 82, 0, 0, Math.PI * 2); g.fill();
  g.fillStyle = "#0f172a"; g.font = "italic 900 120px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("24", 640, 156);
  g.font = "italic 900 40px Inter, Arial"; g.textAlign = "left"; g.fillStyle = "#fde047";
  g.fillText("AUTONOMOUS", 90, 120);
  g.fillStyle = "#f8fafc"; g.fillText("RALLY · GP", 90, 166);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// Pieza extruida a lo ancho a partir de un perfil lateral (x adelante, y arriba)
function extruir(perfil, ancho, mat, bisel = 0.03) {
  const s = new THREE.Shape();
  s.moveTo(perfil[0][0], perfil[0][1]);
  for (const [x, y] of perfil.slice(1)) s.lineTo(x, y);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: Math.max(ancho - 2 * bisel, 0.01), bevelEnabled: true,
    bevelThickness: bisel, bevelSize: bisel, bevelSegments: 3 });
  geo.translate(0, 0, -Math.max(ancho - 2 * bisel, 0.01) / 2);
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = true;
  return m;
}

function crearRueda(ancho, rin) {
  const giro = new THREE.Group();
  const llanta = new THREE.Mesh(new THREE.TorusGeometry(R_LLANTA - 0.06, 0.065, 14, 36),
    new THREE.MeshStandardMaterial({ color: 0x0b0b0b, roughness: 0.9 }));
  llanta.scale.z = ancho / 0.13;
  llanta.castShadow = true;
  giro.add(llanta);
  const centro = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, ancho * 0.9, 16), rin);
  centro.rotation.x = Math.PI / 2;
  giro.add(centro);
  for (let k = 0; k < 6; k++) {   // rin de seis rayos
    const rayo = new THREE.Mesh(new THREE.BoxGeometry(0.03, R_LLANTA - 0.1, 0.03), rin);
    rayo.position.y = (R_LLANTA - 0.1) / 2;
    const brazo = new THREE.Group();
    brazo.rotation.z = (k * Math.PI) / 3;
    brazo.add(rayo);
    giro.add(brazo);
  }
  // Disco de freno
  const disco = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.01, 28),
    new THREE.MeshStandardMaterial({ color: 0x9ca3af, metalness: 0.9, roughness: 0.35 }));
  disco.rotation.x = Math.PI / 2;
  disco.position.z = ancho * 0.45;
  giro.add(disco);
  return giro;
}

function crearPiloto(traje, casco) {
  // El piloto agachado (posición de carrera). Su grupo se desplaza hacia el interior de la curva.
  const p = new THREE.Group();
  const add = (geo, mat, x, y, z, rx = 0, ry = 0, rz = 0) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.castShadow = true; p.add(m); return m;
  };
  const negro = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.7 });
  // Torso inclinado hacia adelante, cadera sobre el asiento
  add(new THREE.CapsuleGeometry(0.17, 0.42, 6, 14), traje, -0.12, 0.98, 0, 0, 0, -1.15);
  // Joroba aerodinámica del traje
  add(new THREE.SphereGeometry(0.13, 14, 10), traje, -0.3, 1.08, 0);
  // Casco con visera
  add(new THREE.SphereGeometry(0.15, 20, 16), casco, 0.2, 1.15, 0);
  add(new THREE.SphereGeometry(0.152, 20, 16, -0.9, 1.8, 1.0, 0.75), new THREE.MeshPhysicalMaterial({
    color: 0x0b1220, metalness: 0.5, roughness: 0.05, clearcoat: 1 }), 0.205, 1.15, 0, 0, Math.PI / 2, 0);
  // Brazos hacia el manubrio y piernas dobladas sobre los estribos
  for (const z of [0.17, -0.17]) {
    add(new THREE.CapsuleGeometry(0.055, 0.32, 4, 8), traje, 0.22, 0.95, z, 0, 0, -0.9);
    add(new THREE.CapsuleGeometry(0.075, 0.34, 4, 8), traje, -0.18, 0.7, z * 1.15, 0, 0, 0.75);
    add(new THREE.CapsuleGeometry(0.065, 0.3, 4, 8), traje, -0.22, 0.47, z * 1.25, 0, 0, -0.5);
    add(new THREE.BoxGeometry(0.2, 0.07, 0.09), negro, -0.13, 0.33, z * 1.25);   // bota
  }
  return p;
}

// Devuelve el grupo, las ruedas (mismo formato que el carro: pivote → giro) y las luces.
export function crearMoto({ largo: L = 2.1, ejes = 1.45 } = {}) {
  const grupo = new THREE.Group();
  const pintura = new THREE.MeshPhysicalMaterial({ map: texturaCarenado(), metalness: 0.5, roughness: 0.25,
    clearcoat: 1, clearcoatRoughness: 0.05 });
  const azul = new THREE.MeshPhysicalMaterial({ color: 0x1d4ed8, metalness: 0.5, roughness: 0.3, clearcoat: 1 });
  const negro = new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 0.55, metalness: 0.3 });
  const dorado = new THREE.MeshStandardMaterial({ color: 0xc9a227, metalness: 0.9, roughness: 0.25 });
  const metal = new THREE.MeshStandardMaterial({ color: 0xb6bcc8, metalness: 0.95, roughness: 0.3 });
  const xf = ejes / 2, xt = -ejes / 2;

  // Carenado principal: perfil lateral de una moto de velocidad
  const carenado = extruir([[0.95, 0.42], [1.02, 0.62], [0.9, 0.86], [0.62, 0.98], [0.3, 0.86], [-0.05, 0.62],
    [-0.15, 0.4], [0.15, 0.28], [0.6, 0.27]], 0.42, pintura);
  const uv = carenado.geometry.attributes.uv, pos = carenado.geometry.attributes.position, nor = carenado.geometry.attributes.normal;
  for (let i = 0; i < pos.count; i++) {    // la decoración se proyecta en los costados
    const u0 = (pos.getX(i) + 0.2) / 1.25;
    uv.setXY(i, nor.getZ(i) < -0.5 ? 1 - u0 : u0, (pos.getY(i) - 0.25) / 0.75);
  }
  grupo.add(carenado);
  // Tanque, asiento y colín
  grupo.add(extruir([[0.35, 0.86], [0.1, 0.95], [-0.25, 0.88], [-0.3, 0.72], [0.2, 0.7]], 0.36, azul));
  const asiento = extruir([[-0.25, 0.86], [-0.55, 0.88], [-0.6, 0.8], [-0.28, 0.78]], 0.26, negro, 0.02);
  grupo.add(asiento);
  grupo.add(extruir([[-0.5, 0.86], [-1.0, 1.0], [-1.05, 0.93], [-0.65, 0.74], [-0.45, 0.74]], 0.26, pintura, 0.025));
  // Cúpula (parabrisas)
  const cupula = extruir([[0.92, 0.88], [0.72, 1.06], [0.58, 1.02], [0.75, 0.86]], 0.3,
    new THREE.MeshPhysicalMaterial({ color: 0x93c5fd, transparent: true, opacity: 0.45, roughness: 0.05, metalness: 0.1 }), 0.015);
  grupo.add(cupula);
  // Alerones laterales del carenado (aerodinámica)
  for (const z of [0.23, -0.23]) {
    const al = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.03, 0.1), negro);
    al.position.set(0.8, 0.58, z * 1.05);
    al.castShadow = true;
    grupo.add(al);
  }
  // Basculante y escape
  for (const z of [0.12, -0.12]) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.07, 0.05), metal);
    b.position.set(xt / 2 - 0.02, 0.38, z);
    b.rotation.z = 0.12;
    grupo.add(b);
  }
  const escape = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.065, 0.55, 14), metal);
  escape.rotation.z = Math.PI / 2 - 0.25;
  escape.position.set(-0.62, 0.62, -0.17);
  grupo.add(escape);

  // Luces: faro delantero y luz de freno en el colín
  const faroMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 3 });
  for (const z of [0.07, -0.07]) {
    const f = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.05, 0.08), faroMat);
    f.position.set(1.0, 0.66, z);
    grupo.add(f);
  }
  const luzFreno = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0xff1e1e, emissiveIntensity: 0.6 });
  const freno = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.05, 0.16), luzFreno);
  freno.position.set(-1.04, 0.95, 0);
  grupo.add(freno);

  // Ruedas: la delantera cuelga de la horquilla (pivote de dirección)
  const ruedas = [];
  for (const [x, delantera, ancho] of [[xf, true, 0.12], [xt, false, 0.16]]) {
    const pivote = new THREE.Group();
    pivote.position.set(x, R_LLANTA, 0);
    const giro = crearRueda(ancho, dorado);
    pivote.add(giro);
    if (delantera) {   // barras de la horquilla, inclinadas hacia atrás
      for (const z of [0.09, -0.09]) {
        const barra = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.62, 10), dorado);
        barra.position.set(-0.12, 0.28, z);
        barra.rotation.z = 0.42;
        pivote.add(barra);
      }
      const manubrio = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.03, 0.5), negro);
      manubrio.position.set(-0.24, 0.55, 0);
      pivote.add(manubrio);
    }
    grupo.add(pivote);
    ruedas.push({ pivote, giro, delantera, radio: R_LLANTA });
  }

  const piloto = crearPiloto(
    new THREE.MeshStandardMaterial({ color: 0x1e3a8a, roughness: 0.55, metalness: 0.15 }),
    new THREE.MeshPhysicalMaterial({ color: 0xfacc15, metalness: 0.4, roughness: 0.2, clearcoat: 1 }));
  grupo.add(piloto);

  const faro = new THREE.SpotLight(0xfff3c4, 0, 60, 0.4, 0.6, 1.2);
  faro.position.set(L / 2, 0.7, 0);
  faro.target.position.set(L / 2 + 10, 0, 0);
  grupo.add(faro, faro.target);
  return { grupo, ruedas, luzFreno, faro, piloto };
}
