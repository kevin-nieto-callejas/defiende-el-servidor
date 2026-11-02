// Texturas fotográficas (PBR) y cielos HDR de Poly Haven (polyhaven.com, licencia
// CC0: se pueden usar libremente). Se cargan desde su CDN al abrir el visor; no se
// guardan en el repositorio. Si no hay internet, cada material queda con su color.

import * as THREE from "three";
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";

const PH = "https://dl.polyhaven.org/file/ph-assets";

// Registro de descargas pesadas (para el indicador de carga del visor)
export const cargas = new Map();   // nombre -> "cargando" | "ok" | "error"
export function registrar(nombre, promesa) {
  cargas.set(nombre, "cargando");
  promesa.then(() => cargas.set(nombre, "ok"), (e) => { cargas.set(nombre, "error"); console.warn("Falló la carga:", nombre, e); });
  return promesa;
}
const cargador = new THREE.TextureLoader();
cargador.setCrossOrigin("anonymous");
const cache = new Map();

function cargar(url, srgb) {
  if (!cache.has(url)) {
    cache.set(url, cargador.loadAsync(url).then((t) => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.anisotropy = 8;
      if (srgb) t.colorSpace = THREE.SRGBColorSpace;
      return t;
    }));
  }
  return cache.get(url);
}

// Aplica una textura PBR de Poly Haven a un material existente (no bloquea:
// el material se ve con su color mientras llegan las imágenes). Con color: false
// solo pone el relieve y la rugosidad (el color sigue siendo el del material).
export function pbr(material, nombre, { repetir = [1, 1], relieve = 1, rugosidad = true, res = "1k", color = true } = {}) {
  const url = (mapa) => `${PH}/Textures/jpg/${res}/${nombre}/${nombre}_${mapa}_${res}.jpg`;
  const pedidos = [cargar(url("diff"), true), cargar(url("nor_gl"), false)];
  if (rugosidad) pedidos.push(cargar(url("rough"), false));
  return registrar("textura " + nombre, Promise.all(pedidos)).then(([diff, nor, rough]) => {
    for (const t of [diff, nor, rough]) if (t) { t.repeat.set(...repetir); }
    // Cada material usa su propia copia (para repetir distinto sin afectar a otros)
    if (color) { material.map = diff.clone(); material.map.repeat.set(...repetir); material.map.needsUpdate = true; }
    material.normalMap = nor.clone(); material.normalMap.repeat.set(...repetir); material.normalMap.needsUpdate = true;
    material.normalScale.set(relieve, relieve);
    if (rough) { material.roughnessMap = rough.clone(); material.roughnessMap.repeat.set(...repetir); material.roughnessMap.needsUpdate = true; }
    if (color) material.color.set(0xffffff);
    material.needsUpdate = true;
    return material;
  }).catch((e) => { console.warn("Textura no disponible:", nombre, e); return material; });
}

// Cielo HDR "puresky" (sin suelo). Devuelve la textura y la dirección del sol,
// que se estima buscando el píxel más brillante de la imagen.
export async function cielo(nombre, res = "2k") {
  const tex = await registrar("cielo " + nombre, new RGBELoader().loadAsync(`${PH}/HDRIs/hdr/${res}/${nombre}_${res}.hdr`));
  tex.mapping = THREE.EquirectangularReflectionMapping;
  const { width: w, height: h, data } = tex.image;
  const leer = data instanceof Uint16Array ? THREE.DataUtils.fromHalfFloat : (v) => v;
  let mejor = -1, mx = 0, my = 0;
  for (let y = 0; y < h / 2; y++) {          // solo la mitad de arriba (el cielo)
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const l = 0.2126 * leer(data[i]) + 0.7152 * leer(data[i + 1]) + 0.0722 * leer(data[i + 2]);
      if (l > mejor) { mejor = l; mx = x; my = y; }
    }
  }
  // Mapeo equirectangular de three.js: u = atan2(dir.z, dir.x)/(2π) + 0.5, v = asin(dir.y)/π + 0.5
  const fi = (mx / w - 0.5) * 2 * Math.PI, theta = (0.5 - my / h) * Math.PI;
  const sol = new THREE.Vector3(Math.cos(theta) * Math.cos(fi), Math.sin(theta), Math.cos(theta) * Math.sin(fi));
  if (sol.y < 0.08) { sol.y = 0.08; sol.normalize(); }  // que el sol nunca quede bajo el horizonte
  return { tex, sol, brillo: mejor };
}
