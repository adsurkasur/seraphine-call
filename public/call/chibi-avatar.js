/* Lightweight Sera renderer. No generated artwork, canvas engine, or runtime dependency. */
(() => {
  'use strict';
  const EXPRESSIONS = new Set(['neutral','happy','playful','serious','concerned','confused']);
  const normalizeExpression = value => EXPRESSIONS.has(value) ? value : 'neutral';
  class MouthGate {
    constructor() { this.reset(); }
    reset() { this.level=0; this.peak=.06; this.open=false; this.held=0; }
    update(rms, dt) {
      this.peak=Math.max(rms,this.peak*Math.exp(-dt/900));
      this.level += (rms-this.level)*(1-Math.exp(-dt/15));
      this.held=Math.max(0,this.held-dt);
      if(!this.open && !this.held && this.level>Math.max(.022,this.peak*.50)) {this.open=true;this.held=60;}
      else if(this.open && !this.held && this.level<Math.max(.016,this.peak*.40)) {this.open=false;this.held=45;}
      return this.open;
    }
  }
  class SpeechInterruptGate {
    constructor(){this.held=0;this.gap=0;this.noise=.004;}
    update(rms,dt){
      dt=Math.min(60,Math.max(0,dt));
      if(rms<.012)this.noise+=(rms-this.noise)*(1-Math.exp(-dt/1200));
      const threshold=Math.max(.018,this.noise*2.5);
      if(rms>=threshold){this.held+=dt;this.gap=0;}
      else if(rms<threshold*.65){this.gap+=dt;if(this.gap>90)this.held=0;}
      return this.held>=160;
    }
  }
  class AudioRing {
    constructor(canvas) {
      this.canvas=canvas;this.context=canvas.getContext('2d');this.level=0;
      this.reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
    }
    draw({state,analyser,now}) {
      const colors={idle:'139,155,180',ended:'139,155,180',muted:'245,158,11',listening:'16,185,129',thinking:'99,102,241',speaking:'56,189,248'};
      const color=colors[state]||colors.idle;
      if(state==='thinking'&&this.previousState!=='thinking')this.thinkingSince=now;
      this.previousState=state;
      const thinking=state==='thinking'&&!this.reducedMotion.matches;
      const thinkingTime=thinking?Math.max(0,now-this.thinkingSince):0;
      const rotation=thinkingTime/18000*Math.PI*2;
      let rms=0;
      if(analyser) {
        if(this.source!==analyser) {
          this.source=analyser;this.wave=new Float32Array(analyser.fftSize);this.bins=new Uint8Array(analyser.frequencyBinCount);
        }
        analyser.getFloatTimeDomainData(this.wave);analyser.getByteFrequencyData(this.bins);
        for(const value of this.wave)rms+=value*value;
        rms=Math.sqrt(rms/this.wave.length);
      }
      this.rms=rms;
      const dt=Math.min(100,now-(this.lastFrame||now));this.lastFrame=now;
      const target=Math.min(1,rms*6);
      this.level=analyser?this.level+(target-this.level)*(1-Math.exp(-dt/65)):0;
      this.canvas.dataset.state=state;this.canvas.dataset.level=this.level.toFixed(4);
      const w=this.canvas.clientWidth,h=this.canvas.clientHeight,dpr=Math.min(2,window.devicePixelRatio||1);
      if(!w||!h)return;
      const pw=Math.round(w*dpr),ph=Math.round(h*dpr);
      if(this.canvas.width!==pw||this.canvas.height!==ph){this.canvas.width=pw;this.canvas.height=ph;}
      const c=this.context;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
      const scale=this.reducedMotion.matches?1:1+this.level*.09;
      this.canvas.dataset.scale=scale.toFixed(4);
      const x=w/2,y=h*.46,r=Math.min(w,h)*.34*scale;
      const glow=c.createRadialGradient(x,y,r*.35,x,y,r*1.35);
      glow.addColorStop(0,`rgba(${color},0.04)`);glow.addColorStop(.7,`rgba(${color},${.09+this.level*.16})`);glow.addColorStop(1,`rgba(${color},0)`);
      c.fillStyle=glow;c.fillRect(0,0,w,h);
      c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.strokeStyle=`rgba(${color},${.28+this.level*.4})`;c.lineWidth=1.5;c.stroke();
      c.lineCap='round';c.lineWidth=2.5;
      for(let i=0;i<48;i++) {
        const angle=i/48*Math.PI*2-Math.PI/2+rotation;
        const frequency=analyser?this.bins[Math.floor(i/48*this.bins.length*.4)]/255:0;
        const wave=thinking?3+10*(.5+.5*Math.sin(i/48*Math.PI*6-thinkingTime/850)):0;
        const amp=wave+this.level*(5+frequency*29)*(this.reducedMotion.matches ? .5 : 1);
        c.beginPath();c.moveTo(x+Math.cos(angle)*(r+4),y+Math.sin(angle)*(r+4));
        c.lineTo(x+Math.cos(angle)*(r+6+amp),y+Math.sin(angle)*(r+6+amp));
        c.strokeStyle=`rgba(${color},${.35+this.level*.5})`;c.stroke();
      }
    }
  }
  class Avatar {
    constructor(element,audio,manifestUrl='/assets/manual-ready-v1/manifest.json') {
      this.element=element;this.audio=audio;this.manifestUrl=manifestUrl;
      this.reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');this.activity='idle';this.expression='neutral';this.gate=new MouthGate();this.images=new Map();this.blinking=false;this.nextBlink=0;
      this.element.dataset.activity='idle';this.element.dataset.lipsync='unavailable';this.element.dataset.ready='loading';
      this.element.textContent='Loading Sera…';
      this.ready=this.load();
      for(const event of ['ended','pause','emptied','error','waiting'])audio.addEventListener(event,()=>{this.gate.reset();this.render();});
      this.tick=this.tick.bind(this);this.frame=requestAnimationFrame(this.tick);
    }
    async load() {
      try {
        const response=await fetch(this.manifestUrl);if(!response.ok)throw Error('Avatar manifest unavailable');
        this.manifest=await response.json();this.baseUrl=new URL('.',new URL(this.manifestUrl,location.href));
        const m=this.manifest,entries=[];
        for(const [name,v] of Object.entries(m.expressions)){entries.push([name+'_closed',v.closed],[name+'_open',v.open]);}
        for(const [name,file] of Object.entries(m.states))entries.push([name,file]);
        entries.push(['neutral_blink',m.blink.neutral_closed]);
        if(m.blink.neutral_open)entries.push(['neutral_blink_open',m.blink.neutral_open]);
        const loadImage=async([key,file])=>{
          if(!/^[a-z_]+\.png$/.test(file))throw Error('Invalid sprite path');
          const img=new Image();img.alt='';img.draggable=false;img.src=new URL(file,this.baseUrl).href;
          try {await img.decode();this.images.set(key,img);}catch(error){console.warn('Sera sprite unavailable:',key);}
        };
        const neutral=entries.find(([key])=>key==='neutral_closed');
        if(!neutral)throw Error('Neutral sprite missing from manifest');
        await loadImage(neutral);
        if(!this.images.has('neutral_closed'))throw Error('Neutral sprite unavailable');
        this.element.dataset.ready='true';this.render();
        await Promise.all(entries.filter(([key])=>key!=='neutral_closed').map(loadImage));
        this.render();
      }catch(error){this.element.dataset.ready='error';this.element.textContent='Sera’s avatar could not load. Your call controls are still available.';console.warn(error);}
    }
    connectAudio(context) {
      if(this.source)return;
      try {
        // Prepare analyser before rerouting media, so an unsupported analyser leaves normal playback intact.
        const analyser=context.createAnalyser();analyser.fftSize=512;
        const data=new Float32Array(analyser.fftSize);
        const source=context.createMediaElementSource(this.audio);
        source.connect(context.destination);source.connect(analyser);
        this.source=source;this.analyser=analyser;this.samples=data;this.element.dataset.lipsync='audio-energy';
      }catch(error){this.element.dataset.lipsync='unavailable';console.warn('Lip sync unavailable; mouth stays closed.',error);}
    }
    setActivity(value) {
      this.activity=['listening','thinking','speaking','ended'].includes(value)?value:'idle';
      this.element.dataset.activity=this.activity;
      if(this.activity!=='speaking')this.gate.reset();
      this.render();
    }
    blink(now=performance.now(),ms=140){this.blinking=true;this.blinkEnd=now+ms;}
    setExpression(value) {this.expression=normalizeExpression(value);this.gate.reset();this.render();}
    tick(now) {
      const dt=Math.min(100,now-(this.lastTick||now));this.lastTick=now;
      if(this.activity==='speaking' && !this.audio.paused && !this.audio.ended && this.audio.readyState>=3 && this.analyser) {
        this.analyser.getFloatTimeDomainData(this.samples);let sum=0;
        for(const sample of this.samples)sum+=sample*sample;
        const rms=Math.sqrt(sum/this.samples.length);
        this.gate.update(rms,dt);
      }else this.gate.reset();
      if(!this.nextBlink)this.nextBlink=now+2500+Math.random()*3500;
      if(this.blinking&&now>=this.blinkEnd){this.blinking=false;this.nextBlink=now+2500+Math.random()*3500;}
      else if(!this.blinking&&now>=this.nextBlink)this.blink(now);
      this.onFrame?.(now);
      this.render();this.frame=requestAnimationFrame(this.tick);
    }
    render() {
      if(!this.images.size)return;
      let key='neutral_closed';
      const mouth=this.gate.open?'open':'closed';
      if(this.activity==='listening'||this.activity==='thinking'||this.activity==='ended')key=this.activity;
      else if(this.activity==='speaking'&&this.expression!=='neutral'&&this.manifest.expressions[this.expression])key=this.expression==='confused'?'confused':this.expression+'_'+mouth;
      else key='neutral_'+mouth; // idle and neutral speech
      // Blink is a separate flag: only neutral has eye art, and it keeps the mouth state.
      if(this.blinking&&key.startsWith('neutral_')&&this.images.has('neutral_blink'+(mouth==='open'?'_open':'')))key='neutral_blink'+(mouth==='open'?'_open':'');
      if(!this.images.has(key))key='neutral_'+mouth;
      if(!this.images.has(key))key='neutral_closed';
      this.element.dataset.expression=this.expression;this.element.dataset.mouth=mouth;this.element.dataset.blink=this.blinking?'on':'off';
      const image=this.images.get(key);
      if(!image)return;
      if(this.element.firstElementChild!==image) {
        const previous=this.element.firstElementChild;
        const stoppedMouth=this.key?.endsWith('_open')&&(this.audio.paused||this.audio.ended||this.activity!=='speaking');
        this.element.replaceChildren(image);this.key=key;this.element.dataset.sprite=key;
        // Full-frame opacity only: never change artwork geometry or positioning.
        if(previous?.tagName==='IMG'&&!this.reducedMotion.matches&&!stoppedMouth){
          const ghost=previous.cloneNode();ghost.className='sprite-outgoing';ghost.setAttribute('aria-hidden','true');this.element.append(ghost);
          ghost.animate([{opacity:1},{opacity:0}],{duration:45,easing:'linear'}).onfinish=()=>ghost.remove();
        }
      }
    }
    destroy() {cancelAnimationFrame(this.frame);this.gate.reset();this.source?.disconnect();}
  }
  window.SeraChibi={Avatar,MouthGate,AudioRing,SpeechInterruptGate,normalizeExpression};
})();
