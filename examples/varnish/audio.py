import json,subprocess,numpy as np,wave,os
HERE=os.path.dirname(os.path.abspath(__file__))
SR=44100
cfg=json.load(open(HERE+'/sfx.json'));DUR=cfg['dur'];N=int(DUR*SR)
mix=np.zeros(N,np.float32)
def rd(p): return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','1','-ar',str(SR),'-']),np.float32)
vo=rd(HERE+'/assets/vo.wav');i=int(cfg['pre']*SR);mix[i:i+len(vo)]+=vo[:N-i]*1.6
rng=np.random.default_rng(1)
def env(L,a): t=np.arange(L)/SR; return t,np.exp(-t*a)
def pop():
    t,e=env(int(.12*SR),38); f=520*np.exp(-t*9)+180; return np.sin(2*np.pi*np.cumsum(f)/SR)*e*.18
def squish():
    t,e=env(int(.25*SR),14); f=140+60*np.sin(t*40); return (np.sin(2*np.pi*np.cumsum(f)/SR)*.5+rng.standard_normal(len(t))*.15)*e*.35
def whoosh():
    L=int(.45*SR);n=rng.standard_normal(L);k=np.convolve(n,np.ones(30)/30,'same');t=np.arange(L)/L;return k*np.sin(np.pi*t)**2*.5
def dab():
    t,e=env(int(.06*SR),70); return rng.standard_normal(len(t))*e*.05
def plip():
    t,e=env(int(.15*SR),30); f=900+1400*np.exp(-t*40); return np.sin(2*np.pi*np.cumsum(f)/SR)*e*.12
def tick():
    t,e=env(int(.04*SR),150); return np.sin(2*np.pi*2500*t)*e*.08
FX=dict(pop=pop,squish=squish,whoosh=whoosh,dab=dab,plip=plip,tick=tick)
for t,k in cfg['sfx']:
    s=FX[k](); i=int(t*SR)
    if 0<=i<N: L=min(len(s),N-i); mix[i:i+L]+=s[:L]
notes=[261.63,293.66,329.63,392.0,440.0,523.25];prog=[[0,2,4],[1,3,5],[0,2,3],[2,4,5]]
tp=np.arange(int(1.2*SR))/SR;k=0;tt=0
while tt<DUR-.5:
    ch=prog[(k//8)%4];fr=notes[ch[k%3]]*(.5 if k%4==0 else 1)
    tone=(np.sin(2*np.pi*fr*tp)+.3*np.sin(2*np.pi*fr*4*tp)*np.exp(-tp*12))*np.exp(-tp*4.5)
    i=int(tt*SR);L=min(len(tone),N-i);mix[i:i+L]+=tone[:L]*.03;k+=1;tt+=.5
mix/=max(1,np.abs(mix).max()/.95)
with wave.open(HERE+'/out_audio.wav','wb') as w: w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((mix*32767).astype(np.int16).tobytes())

subprocess.run(['ffmpeg','-y','-v','error','-i',HERE+'/out_video.mp4','-i',HERE+'/out_audio.wav','-af','loudnorm=I=-16:TP=-1.5','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-shortest','-movflags','+faststart',HERE+'/final.mp4'],check=True)
print('final:',HERE+'/final.mp4')
