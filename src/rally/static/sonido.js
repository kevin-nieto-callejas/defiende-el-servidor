// Sonido del visor, todo sintetizado con Web Audio (no hay archivos de audio).
//
// El motor es el protagonista: sus revoluciones salen de la velocidad real del episodio con una caja
// de cambios simulada, y el acelerador del agente abre o cierra el filtro. Alrededor: llantas que
// chillan cuando el simulador marca derrape, grava al salirse, rocío con lluvia, viento, público
// que se oye más frente a las graderías, eco en el túnel, cuenta regresiva, fanfarria al terminar
// la vuelta y golpe al chocar. Con la cámara de TV el carro pasa de lado: se oye lejos, con efecto
// Doppler y paneo estéreo. Volúmenes por canal en el botón 🔊 (se guardan en este navegador).

const CLAVE = "rally-sonido";
const DEFECTO = { general: 0.8, motor: 1, llantas: 0.8, publico: 0.6, efectos: 0.8, silencio: false, cuenta: true };
const CANALES = [["general", "General"], ["motor", "Motor"], ["llantas", "Llantas y viento"],
                 ["publico", "Público"], ["efectos", "Efectos"]];
// Rally de 4 cilindros con turbo y MotoGP de 4 cilindros: 2 explosiones por vuelta del cigüeñal
const MOTORES = {
  carro: { ralenti: 950, corte: 7800, cambios: [0.24, 0.39, 0.54, 0.69, 0.84, 1.0], turbo: true, brillo: 1 },
  moto: { ralenti: 1800, corte: 16000, cambios: [0.3, 0.45, 0.59, 0.72, 0.86, 1.0], turbo: false, brillo: 1.6 },
};
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

function leerAjustes() {
  try { return { ...DEFECTO, ...JSON.parse(localStorage.getItem(CLAVE) || "{}") }; } catch { return { ...DEFECTO }; }
}
function guardarAjustes(a) {
  try { localStorage.setItem(CLAVE, JSON.stringify(a)); } catch { /* modo privado: solo dura esta visita */ }
}

export function crearSonido({ acciones, escena }) {
  const ajustes = leerAjustes();
  let ctx = null, red = null;              // se crean con el primer toque (los navegadores lo exigen)
  const panel = montarPanel();
  const cuentaEl = document.createElement("div");
  cuentaEl.id = "cuenta-regresiva";
  cuentaEl.className = "oculto";
  escena.appendChild(cuentaEl);

  // ---------------------------------------------------------------- arranque
  function despertar() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      ctx = new AC({ latencyHint: "interactive" });
      red = construirRed();
      aplicarVolumenes();
    }
    if (ctx.state === "suspended") ctx.resume();
    panel.boton.classList.toggle("dormido", false);
  }
  for (const ev of ["pointerdown", "keydown", "touchend"]) addEventListener(ev, despertar, { passive: true });
  document.addEventListener("visibilitychange", () => {
    if (!ctx) return;
    if (document.hidden) ctx.suspend(); else ctx.resume();
  });

  // ---------------------------------------------------------------- red de audio
  function ruido(segundos = 2) {
    const b = ctx.createBuffer(1, ctx.sampleRate * segundos, ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return b;
  }
  function fuenteRuido(buf) {
    const s = ctx.createBufferSource();
    s.buffer = buf; s.loop = true;
    s.start(0, Math.random() * buf.duration);
    return s;
  }
  const g = (v = 0) => { const n = ctx.createGain(); n.gain.value = v; return n; };
  const filtro = (tipo, f, q = 0.7) => { const n = ctx.createBiquadFilter(); n.type = tipo; n.frequency.value = f; n.Q.value = q; return n; };
  const cadena = (...nodos) => { for (let i = 0; i < nodos.length - 1; i++) nodos[i].connect(nodos[i + 1]); return nodos[nodos.length - 1]; };

  function construirRed() {
    const blanco = ruido(2);
    const salida = ctx.createDynamicsCompressor();
    salida.threshold.value = -14; salida.ratio.value = 4; salida.attack.value = 0.004; salida.release.value = 0.2;
    const general = g(1);
    cadena(general, salida, ctx.destination);
    // Medidor de la salida (para pruebas: nivel RMS y pico, sin tocar lo que se oye)
    const medidor = ctx.createAnalyser();
    medidor.fftSize = 2048;
    salida.connect(medidor);
    const muestras = new Float32Array(medidor.fftSize);
    globalThis.rallyNivelSonido = () => {
      medidor.getFloatTimeDomainData(muestras);
      let suma = 0, pico = 0;
      for (const x of muestras) { suma += x * x; pico = Math.max(pico, Math.abs(x)); }
      return { rms: Math.sqrt(suma / muestras.length), pico, estado: ctx.state };
    };
    const canal = { motor: g(1), llantas: g(1), publico: g(1), efectos: g(1) };

    // Vehículo: motor y llantas pasan por distancia (volumen y aire), paneo y eco de túnel
    const vehiculo = g(0), aire = filtro("lowpass", 18000), paneo = ctx.createStereoPanner ? ctx.createStereoPanner() : g(1);
    canal.motor.connect(vehiculo); canal.llantas.connect(vehiculo);
    cadena(vehiculo, aire, paneo, general);
    const eco = ctx.createConvolver(), envioEco = g(0);
    eco.buffer = respuestaTunel();
    cadena(paneo, envioEco, eco, general);
    canal.efectos.connect(general);
    const tapaPublico = filtro("lowpass", 20000);
    cadena(canal.publico, tapaPublico, general);

    // Motor: forma de onda con los armónicos de un motor de explosión, un subarmónico que retumba,
    // aspereza de ruido que sigue a las revoluciones, distorsión suave y un filtro que abre el acelerador
    const ondaMotor = ctx.createPeriodicWave(new Float32Array([0, 1, 0.75, 0.55, 0.5, 0.32, 0.28, 0.2, 0.16, 0.12, 0.09, 0.07]),
                                             new Float32Array(12));
    const osc = ctx.createOscillator(); osc.setPeriodicWave(ondaMotor);
    const sub = ctx.createOscillator(); sub.type = "sawtooth";
    const vibra = ctx.createOscillator(); vibra.frequency.value = 6.3;
    const vibraG = g(9); cadena(vibra, vibraG); vibraG.connect(osc.detune); vibraG.connect(sub.detune);
    const mezcla = g(1), subG = g(0.45), aspero = filtro("bandpass", 400, 2.2), asperoG = g(0);
    osc.connect(mezcla); cadena(sub, subG, mezcla); cadena(fuenteRuido(blanco), aspero, asperoG, mezcla);
    const distorsion = ctx.createWaveShaper();
    distorsion.curve = curvaSuave(2.4); distorsion.oversample = "2x";
    const tono = filtro("lowpass", 900, 1.1), motorG = g(0);
    cadena(mezcla, distorsion, tono, motorG, canal.motor);
    // Turbo: silbido que sube con la carga
    const turbo = ctx.createOscillator(); turbo.type = "sine";
    const turboG = g(0); cadena(turbo, turboG, canal.motor);
    for (const o of [osc, sub, vibra, turbo]) o.start();

    // Llantas: rodadura, chillido de derrape (ruido en banda + tono que tiembla), grava y rocío
    const rodar = filtro("lowpass", 350), rodarG = g(0);
    cadena(fuenteRuido(blanco), rodar, rodarG, canal.llantas);
    const chillido = filtro("bandpass", 1900, 3), chillidoG = g(0);
    cadena(fuenteRuido(blanco), chillido, chillidoG, canal.llantas);
    const chillTono = ctx.createOscillator(); chillTono.type = "triangle"; chillTono.frequency.value = 1150;
    const chillLfo = ctx.createOscillator(); chillLfo.frequency.value = 13;
    const chillLfoG = g(45); cadena(chillLfo, chillLfoG, chillTono.frequency);
    const chillTonoG = g(0); cadena(chillTono, chillTonoG, canal.llantas);
    chillTono.start(); chillLfo.start();
    const grava = filtro("lowpass", 700, 1.5), gravaG = g(0), gravaAm = g(0);
    const gravaLfo = ctx.createOscillator(); gravaLfo.type = "square"; gravaLfo.frequency.value = 23;
    cadena(gravaLfo, gravaAm); gravaLfo.start();
    cadena(fuenteRuido(blanco), grava, gravaG, canal.llantas); gravaAm.connect(gravaG.gain);
    const rocio = filtro("highpass", 2500), rocioG = g(0);
    cadena(fuenteRuido(blanco), rocio, rocioG, canal.llantas);
    const viento = filtro("bandpass", 520, 0.6), vientoG = g(0);
    cadena(fuenteRuido(blanco), viento, vientoG, canal.llantas);

    // Lluvia de fondo (no depende del carro)
    const lluviaF = filtro("bandpass", 3200, 0.4), lluviaG = g(0);
    cadena(fuenteRuido(blanco), lluviaF, lluviaG, canal.efectos);

    // Público: murmullo de mucha gente (cuatro bandas que suben y bajan por su cuenta)
    const bandas = [260, 520, 1050, 2100].map((f) => {
      const filt = filtro("bandpass", f, 1.3), ganancia = g(0);
      cadena(fuenteRuido(blanco), filt, ganancia, canal.publico);
      return { filt, ganancia, base: f, nivel: 0.5 };
    });
    return { blanco, general, canal, vehiculo, aire, paneo, envioEco, tapaPublico, osc, sub, aspero, asperoG, tono,
             motorG, turbo, turboG, rodar, rodarG, chillido, chillidoG, chillTono, chillTonoG, gravaG, gravaAm,
             rocioG, viento, vientoG, lluviaG, bandas };
  }

  function curvaSuave(k) {
    const n = 1024, c = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; c[i] = Math.tanh(k * x) / Math.tanh(k); }
    return c;
  }
  function respuestaTunel() {
    // Eco de túnel: ruido que decae en 1.6 s, con las primeras reflexiones marcadas
    const largo = Math.floor(ctx.sampleRate * 1.6), b = ctx.createBuffer(2, largo, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c);
      for (let i = 0; i < largo; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / largo, 3.2);
      for (const ms of [23, 41, 67, 97]) d[Math.floor(ctx.sampleRate * ms / 1000) + c * 7] += 0.8;
    }
    return b;
  }

  function aplicarVolumenes() {
    if (!red) return;
    const t = ctx.currentTime;
    red.general.gain.setTargetAtTime(ajustes.silencio ? 0 : ajustes.general, t, 0.05);
    for (const k of ["motor", "llantas", "publico", "efectos"]) red.canal[k].gain.setTargetAtTime(ajustes[k], t, 0.05);
    panel.boton.textContent = ajustes.silencio || ajustes.general === 0 ? "🔇" : "🔊";
  }

  // ---------------------------------------------------------------- estado del motor
  const m = { marcha: 0, rpm: 950, carga: 0, cpPrevio: null, iPrevio: -1, publico: 0.3, ovacion: 0,
              proximoPito: 0, proximaBocina: 0, rodarHasta: 0 };

  function revoluciones(cfg, v, vmax, marcha) {
    return Math.max(cfg.ralenti, cfg.corte * v / (cfg.cambios[marcha] * vmax * 1.06));
  }

  /**
   * Cada cuadro: `est` es el estado interpolado del episodio; `vista` trae distancia, velocidad radial y
   * paneo del carro respecto de la cámara. `enCuenta`: el carro espera en la salida acelerando en vacío.
   */
  function actualizar(est, { reproduciendo, enCuenta, moto, mojado, enTunel, publicoCerca, vmax, vista, dt }) {
    if (!red || ctx.state !== "running" || !est) return;
    const t = ctx.currentTime, cfg = MOTORES[moto ? "moto" : "carro"], b = est.b;
    // Después de cruzar la meta el carro sigue rodando y se apaga despacio, en vez de enmudecer de golpe
    const rodando = !reproduciendo && !enCuenta ? clamp((m.rodarHasta - performance.now()) / 3500, 0, 1) : 0;
    const activo = reproduciendo || enCuenta || rodando > 0;
    const v = enCuenta ? 0 : rodando > 0 ? est.v * rodando : est.v;

    // Caja de cambios con histéresis: sube cerca del corte, baja cuando las revoluciones caen mucho
    if (est.i < m.iPrevio || est.i === 0) m.marcha = 0;
    let rpm = revoluciones(cfg, v, vmax, m.marcha);
    if (rpm > cfg.corte * 0.93 && m.marcha < cfg.cambios.length - 1) {
      m.marcha++; rpm = revoluciones(cfg, v, vmax, m.marcha);
      if (activo) cambio(cfg, est.accion[0]);
    } else if (m.marcha > 0 && revoluciones(cfg, v, vmax, m.marcha - 1) < cfg.corte * 0.72 && rpm < cfg.corte * 0.5) {
      m.marcha--; rpm = revoluciones(cfg, v, vmax, m.marcha);
      if (activo && est.accion[0] < 0) petardeo(2 + Math.floor(Math.random() * 3));
    }
    let acel = rodando > 0 ? 0 : clamp(est.accion[0], -1, 1);
    if (enCuenta) {   // en la grilla: acelerones en vacío
      const fase = performance.now() / 1000;
      rpm = cfg.ralenti + (cfg.corte * 0.55 - cfg.ralenti) * (0.5 + 0.5 * Math.sin(fase * 5.5) * Math.sin(fase * 1.7));
      acel = 0.6;
    }
    const cargaPrev = m.carga;
    m.carga += (Math.max(acel, 0) - m.carga) * Math.min(1, dt * 10);
    m.rpm += (rpm - m.rpm) * Math.min(1, dt * 14);
    // Soltar el acelerador con el turbo lleno: válvula de alivio
    if (cfg.turbo && activo && cargaPrev > 0.65 && acel < 0.15 && m.rpm > cfg.corte * 0.5) alivio();
    if (activo && acel < -0.2 && m.rpm > cfg.corte * 0.62 && Math.random() < dt * 6) petardeo(1);

    // Doppler y distancia a la cámara
    const doppler = clamp(343 / (343 + vista.radial), 0.8, 1.25);
    const f = (m.rpm / 30) * doppler;
    red.osc.frequency.setTargetAtTime(f, t, 0.02);
    red.sub.frequency.setTargetAtTime(f / 2, t, 0.02);
    red.aspero.frequency.setTargetAtTime(f * 2.5, t, 0.03);
    const rpmN = (m.rpm - cfg.ralenti) / (cfg.corte - cfg.ralenti);
    red.tono.frequency.setTargetAtTime((500 + 2600 * m.carga + 2200 * rpmN) * cfg.brillo, t, 0.04);
    red.motorG.gain.setTargetAtTime(activo ? 0.18 + 0.2 * m.carga + 0.12 * rpmN : 0, t, 0.06);
    red.asperoG.gain.setTargetAtTime(0.25 * m.carga, t, 0.05);
    red.turbo.frequency.setTargetAtTime(1800 + 2600 * m.carga * rpmN, t, 0.1);
    red.turboG.gain.setTargetAtTime(cfg.turbo && activo ? 0.012 * m.carga * rpmN : 0, t, 0.15);

    // Llantas: derrape del simulador, agarre casi al límite, salida de pista, rocío con lluvia, viento
    const rapidez = clamp(v / 12, 0, 1);
    const limite = b.derrape ? 1 : clamp((est.agarre - 0.88) / 0.12, 0, 1) * 0.45;
    const derrape = activo && !enCuenta ? limite * rapidez : 0;
    red.chillidoG.gain.setTargetAtTime(derrape * (mojado ? 0.25 : 0.55), t, 0.04);
    red.chillido.frequency.setTargetAtTime(1500 + 900 * clamp(v / 25, 0, 1), t, 0.1);
    red.chillTonoG.gain.setTargetAtTime(mojado ? 0 : derrape * 0.05, t, 0.04);
    red.chillTono.frequency.setTargetAtTime(950 + 450 * clamp(v / 25, 0, 1), t, 0.15);
    red.rodarG.gain.setTargetAtTime(activo ? 0.28 * clamp(v / 25, 0, 1) : 0, t, 0.08);
    red.rodar.frequency.setTargetAtTime(200 + 500 * clamp(v / 25, 0, 1), t, 0.1);
    const fuera = activo && b.fuera > 0 ? clamp(v / 8, 0, 1) : 0;
    red.gravaG.gain.setTargetAtTime(fuera * 0.35, t, 0.05);
    red.gravaAm.gain.setTargetAtTime(fuera * 0.25, t, 0.05);
    red.rocioG.gain.setTargetAtTime(activo && mojado ? 0.14 * clamp(v / 20, 0, 1) : 0, t, 0.1);
    red.vientoG.gain.setTargetAtTime(activo ? 0.22 * clamp(v / 25, 0, 1.3) ** 2 : 0, t, 0.1);
    red.viento.frequency.setTargetAtTime(380 + 500 * clamp(v / 25, 0, 1), t, 0.2);
    red.lluviaG.gain.setTargetAtTime(mojado ? 0.06 : 0, t, 0.5);

    // Cámara: cerca suena encima; lejos, bajo y apagado (el aire se come los agudos)
    const d = vista.distancia;
    red.vehiculo.gain.setTargetAtTime(clamp(9 / (d + 3), 0.06, 1.15), t, 0.08);
    red.aire.frequency.setTargetAtTime(clamp(22000 / (1 + d / 25), 1200, 20000), t, 0.1);
    if (red.paneo.pan) red.paneo.pan.setTargetAtTime(clamp(vista.paneo, -0.9, 0.9) * clamp(d / 12, 0, 1), t, 0.06);
    red.envioEco.gain.setTargetAtTime(enTunel ? 0.55 : 0, t, 0.25);
    red.tapaPublico.frequency.setTargetAtTime(enTunel ? 500 : 20000, t, 0.3);

    // Público: más fuerte frente a las graderías; la ovación se va apagando
    m.ovacion = Math.max(0, m.ovacion - dt * 0.18);
    const objetivo = (activo ? 0.22 + 0.55 * publicoCerca : 0.15) + m.ovacion;
    m.publico += (objetivo - m.publico) * Math.min(1, dt * 1.5);
    const brillo = 1 + 0.6 * m.ovacion;
    for (const banda of red.bandas) {
      banda.nivel = clamp(banda.nivel + (Math.random() - 0.5) * dt * 3, 0.25, 1);
      banda.ganancia.gain.setTargetAtTime(m.publico * banda.nivel * 0.8, t, 0.2);
      banda.filt.frequency.setTargetAtTime(banda.base * brillo, t, 0.3);
    }
    // Gente que pita y bocinas cuando el carro pasa frente a ellos
    const ahora = performance.now();
    if (activo && publicoCerca > 0.6 && ahora > m.proximoPito) { silbido(0.5 + Math.random() * 0.5); m.proximoPito = ahora + 1500 + Math.random() * 4000; }
    if (activo && publicoCerca > 0.8 && ahora > m.proximaBocina && Math.random() < dt * 0.2) { bocina(); m.proximaBocina = ahora + 20000; }

    // Puerta pasada: campanita
    if (reproduciendo && m.cpPrevio !== null && b.cp > m.cpPrevio && est.i >= m.iPrevio) campanita();
    m.cpPrevio = b.cp; m.iPrevio = est.i;
  }

  // ---------------------------------------------------------------- sonidos cortos
  function nota(f, ini, dur, { tipo = "sawtooth", vol = 0.2, corte = 2600, destino = red.canal.efectos, ataque = 0.01 } = {}) {
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), env = g(0), lp = filtro("lowpass", corte, 1);
    o.type = tipo; o2.type = tipo; o.frequency.value = f; o2.frequency.value = f; o2.detune.value = 7;
    o.connect(lp); o2.connect(lp); cadena(lp, env, destino);
    env.gain.setValueAtTime(0, ini);
    env.gain.linearRampToValueAtTime(vol, ini + ataque);
    env.gain.setTargetAtTime(vol * 0.7, ini + ataque, dur * 0.3);
    env.gain.setTargetAtTime(0, ini + dur, 0.08);
    for (const x of [o, o2]) { x.start(ini); x.stop(ini + dur + 0.6); }
  }
  function rafaga(ini, dur, { f = 1000, q = 1, vol = 0.3, tipo = "bandpass", hasta = null, destino = red.canal.efectos } = {}) {
    const s = ctx.createBufferSource(), filt = filtro(tipo, f, q), env = g(0);
    s.buffer = red.blanco;
    cadena(s, filt, env, destino);
    if (hasta) filt.frequency.exponentialRampToValueAtTime(hasta, ini + dur);
    env.gain.setValueAtTime(vol, ini);
    env.gain.exponentialRampToValueAtTime(0.001, ini + dur);
    s.start(ini, Math.random()); s.stop(ini + dur + 0.05);
  }
  function cambio(cfg, acel) {
    const t = ctx.currentTime;   // corte de encendido al cambiar: el motor se ahoga un instante
    red.motorG.gain.cancelScheduledValues(t);
    red.motorG.gain.setTargetAtTime(0.05, t, 0.01);
    if (acel > 0.5) rafaga(t, 0.08, { f: 300, q: 1, vol: 0.25, destino: red.canal.motor });
    if (cfg.turbo && acel > 0.6) alivio(0.6);
  }
  function alivio(vol = 1) {
    const t = ctx.currentTime;
    if (t < (m.alivioHasta ?? 0)) return;
    m.alivioHasta = t + 0.9;
    rafaga(t, 0.35, { f: 5200, q: 0.8, vol: 0.09 * vol, tipo: "highpass", destino: red.canal.motor });
  }
  function petardeo(n) {
    const t = ctx.currentTime;
    for (let k = 0; k < n; k++) {
      const ini = t + k * (0.05 + Math.random() * 0.07);
      rafaga(ini, 0.06, { f: 250 + Math.random() * 300, q: 0.9, vol: 0.5, tipo: "lowpass", destino: red.canal.motor });
    }
  }
  function campanita() {
    const t = ctx.currentTime;
    nota(1318.5, t, 0.12, { tipo: "sine", vol: 0.12, corte: 8000 });
    nota(1975.5, t + 0.07, 0.25, { tipo: "sine", vol: 0.1, corte: 8000 });
  }
  function silbido(vol) {
    if (!red) return;
    const t = ctx.currentTime, o = ctx.createOscillator(), env = g(0), vib = ctx.createOscillator(), vibG = g(40);
    o.type = "sine";
    const f0 = 1700 + Math.random() * 600;
    o.frequency.setValueAtTime(f0, t);
    o.frequency.linearRampToValueAtTime(f0 * 1.35, t + 0.18);
    o.frequency.linearRampToValueAtTime(f0 * 1.1, t + 0.55);
    vib.frequency.value = 9; cadena(vib, vibG, o.frequency);
    cadena(o, env, red.canal.publico);
    env.gain.setValueAtTime(0, t); env.gain.linearRampToValueAtTime(0.05 * vol, t + 0.05);
    env.gain.setTargetAtTime(0, t + 0.5, 0.06);
    for (const x of [o, vib]) { x.start(t); x.stop(t + 0.9); }
  }
  function bocina() {
    const t = ctx.currentTime;
    for (const f of [349, 440, 523]) nota(f, t, 0.9, { tipo: "sawtooth", vol: 0.04, corte: 1800, destino: red.canal.publico, ataque: 0.03 });
  }
  function aplauso(ini, dur, densidad = 60) {
    const total = Math.floor(dur * densidad);
    for (let k = 0; k < total; k++) {
      const t = ini + Math.random() * dur, decae = 1 - (t - ini) / dur;
      rafaga(t, 0.03 + Math.random() * 0.03, { f: 1100 + Math.random() * 1800, q: 1.2, vol: 0.3 * (0.4 + decae), destino: red.canal.publico });
    }
  }
  function golpe() {
    const t = ctx.currentTime, o = ctx.createOscillator(), env = g(0);
    o.type = "sine";
    o.frequency.setValueAtTime(95, t); o.frequency.exponentialRampToValueAtTime(32, t + 0.45);
    cadena(o, env, red.canal.efectos);
    env.gain.setValueAtTime(0.9, t); env.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
    o.start(t); o.stop(t + 0.65);
    rafaga(t, 0.55, { f: 1800, q: 0.5, vol: 0.6, tipo: "lowpass", hasta: 300 });
    for (const f of [523, 1187, 1873, 2711, 3307]) nota(f * (0.9 + Math.random() * 0.2), t, 0.05 + Math.random() * 0.1,
      { tipo: "triangle", vol: 0.05, corte: 9000 });
    for (let k = 0; k < 6; k++) rafaga(t + 0.15 + Math.random() * 0.5, 0.02, { f: 5000 + Math.random() * 3000, q: 3, vol: 0.12 });
  }
  function exclamacion(fuerte) {
    // "¡Uuuuy!" de la tribuna: el murmullo sube y cae de tono
    const t = ctx.currentTime;
    m.ovacion = Math.max(m.ovacion, fuerte ? 0.5 : 0.3);
    for (const f of [420, 640]) rafaga(t, 1.6, { f, q: 3, vol: fuerte ? 0.35 : 0.2, hasta: f * 0.6, destino: red.canal.publico });
  }

  // ---------------------------------------------------------------- eventos de la carrera
  function cuenta() {
    // Devuelve cuántos ms debe esperar el carro en la salida (0 si la cuenta está apagada)
    if (!ajustes.cuenta) return 0;
    const pasos = ["3", "2", "1", "¡YA!"];
    pasos.forEach((txt, k) => setTimeout(() => {
      cuentaEl.textContent = txt;
      cuentaEl.className = k === 3 ? "ya" : "";
      void cuentaEl.offsetWidth;   // reinicia la animación de cada número
      cuentaEl.classList.add("pulso");
    }, k * 800));
    setTimeout(() => cuentaEl.classList.add("oculto"), 3 * 800 + 700);
    if (red && ctx.state === "running") {
      const t = ctx.currentTime;
      for (let k = 0; k < 3; k++) nota(660, t + k * 0.8, 0.16, { tipo: "square", vol: 0.1, corte: 3000 });
      nota(1320, t + 2.4, 0.55, { tipo: "square", vol: 0.12, corte: 4000 });
      setTimeout(() => { m.ovacion = Math.max(m.ovacion, 0.45); }, 2400);
    }
    return 3 * 800;
  }

  function fin(resultado) {
    if (!red || ctx.state !== "running") return;
    const t = ctx.currentTime;
    if (resultado === "exito") {
      // Fanfarria de bandera a cuadros, ovación y aplausos; el carro sigue rodando y se apaga
      m.rodarHasta = performance.now() + 3500;
      [[392, 0], [523.3, 0.13], [659.3, 0.26], [784, 0.39]].forEach(([f, d]) => nota(f, t + d, 0.14, { vol: 0.24 }));
      for (const f of [523.3, 659.3, 784, 1046.5]) nota(f, t + 0.55, 1.4, { vol: 0.15, corte: 3400 });
      nota(130.8, t + 0.55, 1.4, { vol: 0.18, corte: 900 });   // bajo que sostiene el acorde
      m.ovacion = 1.2;
      aplauso(t + 0.3, 5, 150);
      for (let k = 0; k < 4; k++) setTimeout(() => silbido(1), 400 + k * 450 + Math.random() * 300);
      setTimeout(bocina, 900);
    } else if (resultado === "choque" || resultado === "caida") {
      golpe();
      if (resultado === "caida") rafaga(t, 1.8, { f: 1600, q: 2, vol: 0.4, hasta: 500 });   // la moto se arrastra
      exclamacion(true);
    } else {
      nota(392, t, 0.35, { tipo: "triangle", vol: 0.12, corte: 1500 });
      nota(311, t + 0.35, 0.7, { tipo: "triangle", vol: 0.12, corte: 1500 });
      exclamacion(false);
    }
  }

  // ---------------------------------------------------------------- panel de volúmenes
  function montarPanel() {
    const caja = document.createElement("div");
    caja.className = "sonido-caja";
    caja.innerHTML = `
      <button class="cuadro dormido" id="btn-sonido" aria-label="Sonido" title="Sonido (tecla M)">🔊</button>
      <div id="panel-sonido" class="oculto" role="dialog" aria-label="Volumen">
        <div class="ps-titulo"><b>Sonido</b><label><input type="checkbox" id="ps-silencio"> Silenciar</label></div>
        ${CANALES.map(([k, n]) => `<label class="ps-fila"><span>${n}</span>
          <input type="range" min="0" max="1" step="0.05" data-canal="${k}"><output></output></label>`).join("")}
        <label class="ps-check"><input type="checkbox" id="ps-cuenta"> Cuenta regresiva al iniciar</label>
        <p class="ps-nota">Todo se sintetiza en vivo con la física del episodio: motor y cambios por la velocidad, chillido cuando el simulador marca derrape, Doppler con la cámara de TV.</p>
      </div>`;
    const ayuda = acciones.querySelector(".ayuda-caja");
    acciones.insertBefore(caja, ayuda);
    const boton = caja.querySelector("#btn-sonido"), cuadro = caja.querySelector("#panel-sonido");
    boton.onclick = (e) => { e.stopPropagation(); despertar(); cuadro.classList.toggle("oculto"); };
    addEventListener("pointerdown", (e) => { if (!caja.contains(e.target)) cuadro.classList.add("oculto"); });
    for (const r of caja.querySelectorAll("input[type=range]")) {
      const salida = r.nextElementSibling, k = r.dataset.canal;
      const pintar = () => { salida.textContent = `${Math.round(ajustes[k] * 100)}`; };
      r.value = ajustes[k]; pintar();
      r.oninput = () => { ajustes[k] = parseFloat(r.value); pintar(); guardarAjustes(ajustes); aplicarVolumenes(); };
    }
    const silencio = caja.querySelector("#ps-silencio"), cuentaCk = caja.querySelector("#ps-cuenta");
    silencio.checked = ajustes.silencio; cuentaCk.checked = ajustes.cuenta;
    silencio.onchange = () => { ajustes.silencio = silencio.checked; guardarAjustes(ajustes); aplicarVolumenes(); };
    cuentaCk.onchange = () => { ajustes.cuenta = cuentaCk.checked; guardarAjustes(ajustes); };
    addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" && e.target.type !== "range") return;
      if (e.key === "m" || e.key === "M") { ajustes.silencio = !ajustes.silencio; silencio.checked = ajustes.silencio; guardarAjustes(ajustes); aplicarVolumenes(); }
    });
    boton.textContent = ajustes.silencio ? "🔇" : "🔊";
    return { boton };
  }

  return { actualizar, cuenta, fin };
}
