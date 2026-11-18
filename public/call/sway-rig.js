/* Two-joint whole-PNG mesh. No body cutouts, UI/debug controls, or external runtime. */
(() => {
  'use strict';
  const profiles={
    idle:{body:2.5,head:1,period:5.2,phase:.65,settle:360},
    listening:{body:3.3,head:1.5,period:5.8,phase:1.1,settle:340},
    thinking:{body:6.1,head:2.25,period:4.2,phase:1.6,settle:300},
    speaking:{body:4.5,head:1.7,period:3.8,phase:.85,settle:230},
    ended:{body:1.35,head:1.4,period:7.6,phase:1.9,settle:650}
  };
  const vertex="attribute vec2 point; varying vec2 uv; uniform float bodyAngle,headAngle,headDrop;\nvec2 turn(vec2 p,vec2 pivot,float a){float c=cos(a),s=sin(a);vec2 d=p-pivot;return pivot+vec2(c*d.x-s*d.y,s*d.x+c*d.y);}\nvoid main(){uv=point/vec2(320.,480.);float hw=1.-smoothstep(178.,216.,point.y);float bw=1.-smoothstep(238.,310.,point.y);\nvec2 p=mix(point,turn(point,vec2(157.,190.),headAngle)+vec2(0.,headDrop),hw);p=mix(p,turn(p,vec2(157.,270.),bodyAngle),bw);\ngl_Position=vec4(p.x/160.-1.,1.-p.y/240.,0.,1.);}";
  const fragment="precision mediump float;varying vec2 uv;uniform sampler2D beforeImage,afterImage;uniform float blend;\nvoid main(){vec4 a=texture2D(beforeImage,uv),b=texture2D(afterImage,uv);gl_FragColor=mix(vec4(a.rgb*a.a,a.a),vec4(b.rgb*b.a,b.a),blend);}";
  class SwayRig {
    constructor(onFailure){
      this.canvas=document.createElement('canvas');this.canvas.className='sera-sway';
      this.canvas.setAttribute('aria-hidden','true');this.canvas.width=320;this.canvas.height=480;
      const gl=this.gl=this.canvas.getContext('webgl',{alpha:true,premultipliedAlpha:true,antialias:true});
      if(!gl)throw Error('WebGL unavailable');
      this.textures=new Map();this.shaders=[];this.pose={bodyAngle:0,headAngle:0,headDrop:0};
      this.reduce=matchMedia('(prefers-reduced-motion: reduce)');
      this.canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();this.lost=true;onFailure();});
      try{
        this.program=gl.createProgram();
        for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
          const shader=gl.createShader(type);this.shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
          if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('Mesh shader unavailable');
          gl.attachShader(this.program,shader);
        }
        gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('Mesh program unavailable');gl.useProgram(this.program);
        this.locations=Object.fromEntries(['bodyAngle','headAngle','headDrop','beforeImage','afterImage','blend'].map(k=>[k,gl.getUniformLocation(this.program,k)]));
        const points=[],indices=[],nx=8,ny=40;
        for(let y=0;y<=ny;y++)for(let x=0;x<=nx;x++)points.push(x/nx*320,y/ny*480);
        for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const a=y*(nx+1)+x,b=a+1,c=a+nx+1,d=c+1;indices.push(a,b,c,b,d,c);}
        this.vertexBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.vertexBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(points),gl.STATIC_DRAW);
        const attr=gl.getAttribLocation(this.program,'point');gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,2,gl.FLOAT,false,0,0);
        this.indexBuffer=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,this.indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);this.count=indices.length;
        gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
      }catch(error){this.destroy();throw error;}
    }
    texture(key,image){
      if(this.textures.has(key))return this.textures.get(key);
      const gl=this.gl,t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);
      for(const name of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,name,gl.CLAMP_TO_EDGE);
      for(const name of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,name,gl.LINEAR);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);this.textures.set(key,t);return t;
    }
    draw({key,image,state,level=0,now=performance.now(),instant=false}){
      if(this.lost||document.hidden)return;
      const gl=this.gl,dt=Math.max(0,Math.min(80,now-(this.last||now)));this.last=now;
      const p=profiles[state]||profiles.idle,t=now/1000,cycle=t*2*Math.PI/p.period;
      const osc=.8*Math.sin(cycle)+.2*Math.sin(cycle*.61+.6),emphasis=state==='speaking'?Math.min(1,level*8):0;
      const personality=state==='listening' ? .10 : state==='thinking' ? .13*Math.sin(cycle*.5):0;
      const body=(osc+personality)*p.body*Math.PI/180;
      const head=((Math.sin(cycle*.83+p.phase)*.8+.2*Math.sin(cycle*1.31+.4))*p.head+emphasis*.65*Math.sin(cycle*1.4))*Math.PI/180;
      const drop=state==='ended'?Math.pow(Math.max(0,Math.sin(cycle)),4)*3:0;
      const ease=1-Math.exp(-dt/p.settle);
      for(const [name,target] of [['bodyAngle',body],['headAngle',head],['headDrop',drop]])this.pose[name]=this.reduce.matches?0:this.pose[name]+(target-this.pose[name])*ease;
      const texture=this.texture(key,image);
      if(key!==this.key){this.previous=this.current||texture;this.current=texture;this.key=key;this.switchedAt=now;}
      if(instant||this.reduce.matches)this.previous=this.current;
      const dpr=Math.min(2,devicePixelRatio||1),w=Math.round(this.canvas.clientWidth*dpr),h=Math.round(this.canvas.clientHeight*dpr);
      if(!w||!h)return;
      if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;gl.viewport(0,0,w,h);}
      gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
      for(const name of ['bodyAngle','headAngle','headDrop'])gl.uniform1f(this.locations[name],this.pose[name]);
      gl.uniform1f(this.locations.blend,Math.min(1,(now-this.switchedAt)/45));
      for(const [unit,texture] of [[0,this.previous],[1,this.current]]){gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);}
      gl.uniform1i(this.locations.beforeImage,0);gl.uniform1i(this.locations.afterImage,1);gl.drawElements(gl.TRIANGLES,this.count,gl.UNSIGNED_SHORT,0);
    }
    destroy(){
      const gl=this.gl;if(!gl)return;
      this.textures?.forEach(t=>gl.deleteTexture(t));this.textures?.clear();
      if(this.vertexBuffer)gl.deleteBuffer(this.vertexBuffer);if(this.indexBuffer)gl.deleteBuffer(this.indexBuffer);
      if(this.program)gl.deleteProgram(this.program);this.shaders?.forEach(s=>gl.deleteShader(s));this.lost=true;
    }
  }
  window.SeraSwayRig=SwayRig;
})();
