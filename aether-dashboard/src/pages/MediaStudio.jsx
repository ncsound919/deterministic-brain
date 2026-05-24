import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Image, Video, Music, Play, Pause, SkipForward, SkipBack, Download, Wand2, Plus, Volume2, Layers, Monitor, Smartphone, Square } from 'lucide-react';
import { mediaGenerate, mediaLibrary } from '../api';
import { usePageState } from '../stateManager';

const PROMPT_TEMPLATES = [
  { label: 'Cyberpunk City', prompt: 'A highly detailed cyberpunk city street at night, neon lights, rain reflections, photorealistic, 8k, unreal engine 5' },
  { label: 'Corporate Tech', prompt: 'Modern minimalist corporate office, diverse team collaborating around a glowing holographic table, bright natural lighting, professional photography' },
  { label: 'Abstract Concept', prompt: 'Abstract visual representation of artificial intelligence flowing through a neural network, glowing cyan and magenta nodes, dark background' },
  { label: 'Fantasy Landscape', prompt: 'Epic fantasy mountain landscape at golden hour, ancient ruins, epic sky, cinematic lighting, concept art' }
];

export default function MediaStudio() {
  const [library, setLibrary] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [playing, setPlaying] = useState(null);
  const [pageState, updatePageState] = usePageState('media-studio', {
    prompt: '',
    type: 'image',
    aspectRatio: '1:1',
  });
  const audioRef = useRef(null);

  const refresh = useCallback(async () => {
    const d = await mediaLibrary();
    if (!d._error) setLibrary(d.files || []);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleGenerate = async () => {
    if (!pageState.prompt.trim()) return;
    setGenerating(true);
    await mediaGenerate({ prompt: pageState.prompt, type: pageState.type, aspect_ratio: pageState.aspectRatio });
    updatePageState({ prompt: '' });
    setTimeout(refresh, 5000);
    setGenerating(false);
  };

  const skipTrack = (direction) => {
    const audioFiles = library.filter(f => f.type === 'audio' || f.name?.match(/\.(mp3|wav|ogg)$/i));
    if (audioFiles.length === 0) return;
    const currentIdx = audioFiles.findIndex(f => f.url === playing?.url);
    const nextIdx = direction === 'forward'
      ? (currentIdx + 1) % audioFiles.length
      : (currentIdx - 1 + audioFiles.length) % audioFiles.length;
    const next = audioFiles[Math.max(0, nextIdx)];
    setPlaying({ ...next, isPaused: false });
    if (audioRef.current) {
      audioRef.current.src = next.url;
      audioRef.current.play();
    }
  };

  const togglePlay = (file) => {
    if (playing?.url === file.url) {
      if (audioRef.current.paused) audioRef.current.play();
      else audioRef.current.pause();
      setPlaying({ ...file, isPaused: !audioRef.current.paused });
    } else {
      setPlaying({ ...file, isPaused: false });
      if (audioRef.current) {
        audioRef.current.src = file.url;
        audioRef.current.play();
      }
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
      {/* Studio Controls */}
      <div className="glass panel">
        <div className="panel__header">
          <Wand2 size={16} color="var(--primary)" />
          <span className="panel__title">Media Generator Pro</span>
        </div>
        <div className="panel__body" style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          
          <div style={{ flex: 2, minWidth: 300, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="label">Prompt Engineering</span>
              <select 
                onChange={(e) => updatePageState({ prompt: e.target.value })}
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 4, color: 'var(--text-muted)', fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
              >
                <option value="">Load Template...</option>
                {PROMPT_TEMPLATES.map(t => <option key={t.label} value={t.prompt}>{t.label}</option>)}
              </select>
            </div>
            
            <textarea
              value={pageState.prompt}
              onChange={(e) => updatePageState({ prompt: e.target.value })}
              placeholder="Describe what you want to create in vivid detail..."
              style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--surface-border)', borderRadius: 12, padding: '1rem', color: 'var(--text)', fontSize: '0.9rem', minHeight: 120, fontFamily: "'JetBrains Mono', monospace" }}
            />
          </div>

          <div style={{ flex: 1, minWidth: 250, display: 'flex', flexDirection: 'column', gap: '1.5rem', borderLeft: '1px solid var(--surface-border)', paddingLeft: '1.5rem' }}>
            
            <div>
              <div className="label" style={{ marginBottom: '0.5rem' }}>Asset Type</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {['image', 'video', 'podcast'].map(t => (
                  <button
                    key={t}
                    onClick={() => updatePageState({ type: t })}
                    style={{
                      flex: 1, padding: '0.6rem 0', borderRadius: 8,
                      background: pageState.type === t ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                      border: '1px solid', borderColor: pageState.type === t ? 'var(--primary)' : 'var(--surface-border)',
                      color: pageState.type === t ? '#fff' : 'var(--text-muted)', cursor: 'pointer',
                      fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6
                    }}
                  >
                    {t === 'image' && <Image size={14} />}
                    {t === 'video' && <Video size={14} />}
                    {t === 'podcast' && <Music size={14} />}
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {pageState.type === 'image' && (
              <div>
                <div className="label" style={{ marginBottom: '0.5rem' }}>Aspect Ratio</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => updatePageState({ aspectRatio: '1:1' })} style={{ flex: 1, padding: '0.5rem', borderRadius: 8, background: pageState.aspectRatio === '1:1' ? 'rgba(0,184,255,0.1)' : 'transparent', border: `1px solid ${pageState.aspectRatio === '1:1' ? 'var(--primary)' : 'var(--surface-border)'}`, color: pageState.aspectRatio === '1:1' ? 'var(--primary)' : 'var(--text-muted)', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                    <Square size={16} /> <span style={{ fontSize: '0.65rem' }}>1:1</span>
                  </button>
                  <button onClick={() => updatePageState({ aspectRatio: '16:9' })} style={{ flex: 1, padding: '0.5rem', borderRadius: 8, background: pageState.aspectRatio === '16:9' ? 'rgba(0,184,255,0.1)' : 'transparent', border: `1px solid ${pageState.aspectRatio === '16:9' ? 'var(--primary)' : 'var(--surface-border)'}`, color: pageState.aspectRatio === '16:9' ? 'var(--primary)' : 'var(--text-muted)', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                    <Monitor size={16} /> <span style={{ fontSize: '0.65rem' }}>16:9</span>
                  </button>
                  <button onClick={() => updatePageState({ aspectRatio: '9:16' })} style={{ flex: 1, padding: '0.5rem', borderRadius: 8, background: pageState.aspectRatio === '9:16' ? 'rgba(0,184,255,0.1)' : 'transparent', border: `1px solid ${pageState.aspectRatio === '9:16' ? 'var(--primary)' : 'var(--surface-border)'}`, color: pageState.aspectRatio === '9:16' ? 'var(--primary)' : 'var(--text-muted)', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                    <Smartphone size={16} /> <span style={{ fontSize: '0.65rem' }}>9:16</span>
                  </button>
                </div>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={generating || !pageState.prompt.trim()}
              style={{
                marginTop: 'auto',
                background: 'linear-gradient(135deg, var(--primary), var(--accent))',
                border: 'none', borderRadius: 8, padding: '1rem',
                color: '#fff', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                opacity: generating || !pageState.prompt.trim() ? 0.5 : 1
              }}
            >
              {generating ? 'PROCESSING...' : 'GENERATE ASSET'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--gap-md)' }}>
        {/* Asset Library */}
        <div className="glass panel">
          <div className="panel__header">
            <Layers size={14} color="var(--primary)" />
            <span className="panel__title">Asset Library & History</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '1rem' }}>
              {library.map((file, i) => (
                <div key={i} className="glass" style={{ overflow: 'hidden', cursor: 'pointer', position: 'relative', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ position: 'relative' }}>
                    {file.type === 'image' && <img src={file.url} style={{ width: '100%', height: 140, objectFit: 'cover' }} />}
                    {file.type === 'video' && <div style={{ width: '100%', height: 140, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Video color="var(--text-muted)" size={32} /></div>}
                    {file.type === 'audio' && <div style={{ width: '100%', height: 140, background: 'linear-gradient(135deg, #1e1e2f, #0a0a14)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Music color="var(--primary)" size={32} /></div>}
                    <div style={{ position: 'absolute', top: 5, right: 5, background: 'rgba(0,0,0,0.6)', padding: '2px 6px', borderRadius: 4, fontSize: '0.55rem', fontWeight: 800, color: '#fff' }}>
                      {file.type.toUpperCase()}
                    </div>
                  </div>
                  <div style={{ padding: '0.6rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <div className="mono" style={{ fontSize: '0.65rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: 6 }}>{file.name}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                      <span className="label" style={{ fontSize: '0.55rem' }}>{(file.size / 1024).toFixed(0)} KB</span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {file.type === 'audio' && (
                          <button onClick={() => togglePlay(file)} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}>
                            {playing?.url === file.url && !playing.isPaused ? <Pause size={14} /> : <Play size={14} />}
                          </button>
                        )}
                        <a href={file.url} download={file.name} style={{ color: 'var(--text-muted)' }}><Download size={14} /></a>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {library.length === 0 && (
                <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No assets generated yet.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Audio Player / Radio */}
        <div className="glass panel">
          <div className="panel__header">
            <Music size={14} color="var(--accent)" />
            <span className="panel__title">Aether Radio</span>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '2rem 1rem' }}>
            <div style={{
              width: 140, height: 140, borderRadius: '50%', 
              background: 'linear-gradient(135deg, var(--primary), var(--accent))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: playing && !playing.isPaused ? '0 0 40px rgba(0, 255, 159, 0.4)' : '0 0 20px rgba(0, 184, 255, 0.1)',
              marginBottom: '1.5rem',
              transition: 'box-shadow 0.3s ease',
              animation: playing && !playing.isPaused ? 'pulse 2s infinite' : 'none'
            }}>
              <Volume2 size={56} color="#fff" />
            </div>
            <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text)', marginBottom: 4 }}>{playing?.name || 'No Track Selected'}</div>
              <div className="label">Aether background FM</div>
            </div>
            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
              <button onClick={() => skipTrack('back')} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><SkipBack size={24} /></button>
              <button
                onClick={() => playing && togglePlay(playing)}
                style={{
                  width: 64, height: 64, borderRadius: '50%',
                  background: 'var(--primary)', border: 'none',
                  color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', boxShadow: '0 4px 15px rgba(0,184,255,0.3)'
                }}
              >
                {playing && !playing.isPaused ? <Pause size={28} /> : <Play size={28} style={{ marginLeft: 4 }} />}
              </button>
              <button onClick={() => skipTrack('forward')} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><SkipForward size={24} /></button>
            </div>
            <audio ref={audioRef} hidden />
          </div>
        </div>
      </div>
    </div>
  );
}
