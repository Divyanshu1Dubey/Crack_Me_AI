"use client";

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { 
  Play, Pause, Volume2, VolumeX, Maximize, Minimize, 
  Settings, Captions, RotateCcw, Loader2, PictureInPicture2 
} from 'lucide-react';

interface PremiumVideoPlayerProps {
  src: string;
  subtitlesSrc?: string;
  poster?: string;
  className?: string;
  autoPlay?: boolean;
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

export function PremiumVideoPlayer({ src, subtitlesSrc, poster, className = '', autoPlay = false }: PremiumVideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPictureInPicture, setIsPictureInPicture] = useState(false);
  const [supportsPictureInPicture, setSupportsPictureInPicture] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isHovering, setIsHovering] = useState(false);
  const [canHover, setCanHover] = useState(true);
  
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showSettings, setShowSettings] = useState(false);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  
  const [isBuffering, setIsBuffering] = useState(true);
  const storageKey = `cracklabs-video-position:${src}`;

  useEffect(() => {
    setSupportsPictureInPicture(Boolean(document.pictureInPictureEnabled));
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const mediaQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
    const updateCapability = () => setCanHover(mediaQuery.matches);
    updateCapability();

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', updateCapability);
      return () => mediaQuery.removeEventListener('change', updateCapability);
    }

    mediaQuery.addListener(updateCapability);
    return () => mediaQuery.removeListener(updateCapability);
  }, []);

  // Auto-hide controls when playing and not hovering
  useEffect(() => {
    let timeout: NodeJS.Timeout;
    if (canHover && isPlaying && !isHovering && !showSettings) {
      timeout = setTimeout(() => setShowControls(false), 2000);
    } else {
      setShowControls(true);
    }
    return () => clearTimeout(timeout);
  }, [canHover, isPlaying, isHovering, showSettings]);

  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  }, []);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      setProgress((videoRef.current.currentTime / videoRef.current.duration) * 100);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      setIsBuffering(false);
      setPlaybackRate(videoRef.current.playbackRate || 1);
      setIsMuted(videoRef.current.muted);
      setVolume(videoRef.current.muted ? 0 : videoRef.current.volume || 1);
      const savedTime = Number(window.localStorage.getItem(storageKey) || 0);
      if (savedTime > 5 && savedTime < videoRef.current.duration - 5) {
        videoRef.current.currentTime = savedTime;
      }
    }
  };

  useEffect(() => {
    const tracks = videoRef.current?.textTracks;
    if (tracks && tracks.length > 0) {
      // eslint-disable-next-line react-hooks/immutability
      tracks[0].mode = subtitlesEnabled ? 'showing' : 'hidden';
    }
  }, [subtitlesEnabled, subtitlesSrc]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const savePosition = () => {
      if (video.currentTime > 0 && Number.isFinite(video.currentTime)) {
        window.localStorage.setItem(storageKey, String(Math.floor(video.currentTime)));
      }
    };
    const clearPosition = () => window.localStorage.removeItem(storageKey);
    video.addEventListener('timeupdate', savePosition);
    video.addEventListener('ended', clearPosition);
    return () => {
      savePosition();
      video.removeEventListener('timeupdate', savePosition);
      video.removeEventListener('ended', clearPosition);
    };
  }, [storageKey]);

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    setIsMuted(val === 0);
    if (videoRef.current) {
      videoRef.current.volume = val;
      videoRef.current.muted = val === 0;
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  const togglePictureInPicture = async () => {
    const video = videoRef.current;
    if (!video || !document.pictureInPictureEnabled) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsPictureInPicture(false);
      } else {
        await video.requestPictureInPicture();
        setIsPictureInPicture(true);
      }
    } catch {
      setIsPictureInPicture(false);
    }
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (videoRef.current && duration > 0) {
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;
      videoRef.current.currentTime = pos * duration;
      setProgress(pos * 100);
    }
  };
  
  const skipTime = (amount: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime += amount;
    }
  };

  const changePlaybackRate = (rate: number) => {
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
      setPlaybackRate(rate);
      setShowSettings(false);
    }
  };

  const toggleSubtitles = () => {
    if (videoRef.current) {
      const tracks = videoRef.current.textTracks;
      if (tracks && tracks.length > 0) {
        const newMode = !subtitlesEnabled;
        tracks[0].mode = newMode ? 'showing' : 'hidden';
        setSubtitlesEnabled(newMode);
      }
    }
  };

  const formatTime = (time: number) => {
    if (isNaN(time)) return '0:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input somewhere
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return;

      switch(e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowRight':
          skipTime(10);
          break;
        case 'ArrowLeft':
          skipTime(-10);
          break;
        case 'f':
          toggleFullscreen();
          break;
        case 'p':
          if (supportsPictureInPicture) {
            togglePictureInPicture();
          }
          break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [supportsPictureInPicture, togglePictureInPicture, togglePlay]);

  useEffect(() => {
    const syncFullscreen = () => setIsFullscreen(Boolean(document.fullscreenElement));
    const syncPiP = () => setIsPictureInPicture(Boolean(document.pictureInPictureElement));

    document.addEventListener('fullscreenchange', syncFullscreen);
    document.addEventListener('enterpictureinpicture', syncPiP as EventListener);
    document.addEventListener('leavepictureinpicture', syncPiP as EventListener);

    return () => {
      document.removeEventListener('fullscreenchange', syncFullscreen);
      document.removeEventListener('enterpictureinpicture', syncPiP as EventListener);
      document.removeEventListener('leavepictureinpicture', syncPiP as EventListener);
    };
  }, []);
  
  // Compute VTT URL
  const vttSrc = subtitlesSrc || (src.endsWith('.mp4') ? `${src.slice(0, -4)}.vtt` : '');

  return (
    <div 
      ref={containerRef}
      className={`relative group bg-black rounded-xl overflow-hidden shadow-2xl aspect-video touch-manipulation ${className}`}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      onMouseMove={() => {
        if (canHover) {
          setIsHovering(true);
        }
        // Reset the auto-hide timer
      }}
    >
      <video
        ref={videoRef}
        src={src}
        className="w-full h-full object-contain cursor-pointer"
        onClick={togglePlay}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onWaiting={() => setIsBuffering(true)}
        onPlaying={() => { setIsBuffering(false); setIsPlaying(true); }}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        crossOrigin="anonymous"
        autoPlay={autoPlay}
        poster={poster}
        playsInline
      >
        {vttSrc && (
          <track
            kind="subtitles"
            srcLang="en"
            src={vttSrc}
            default={subtitlesEnabled}
            label="English"
          />
        )}
        Your browser does not support the video tag.
      </video>
      
      {/* Loading Overlay */}
      {isBuffering && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 z-10 pointer-events-none">
          <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
        </div>
      )}
      
      {/* Big Play Button Overlay (when paused and not buffered) */}
      {!isPlaying && !isBuffering && progress === 0 && (
        <div 
          className="absolute inset-0 flex items-center justify-center bg-black/20 z-10 cursor-pointer"
          onClick={togglePlay}
        >
          <div className="bg-indigo-600/80 hover:bg-indigo-600 p-4 rounded-full backdrop-blur transition-transform transform hover:scale-110">
            <Play className="w-10 h-10 text-white fill-current ml-1" />
          </div>
        </div>
      )}

      {/* Controls Overlay */}
      <div 
        className={`absolute bottom-0 left-0 right-0 p-4 pt-16 bg-linear-to-t from-black/90 via-black/50 to-transparent transition-opacity duration-300 z-20 ${
          showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* Progress Bar */}
        <div 
          className="w-full h-1.5 bg-white/20 rounded-full mb-4 cursor-pointer group/progress relative"
          onClick={handleProgressClick}
        >
          <div 
            className="h-full bg-indigo-500 rounded-full relative"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover/progress:opacity-100 transition-opacity" />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 text-white">
          <div className="flex min-w-0 flex-1 items-center gap-3 sm:gap-4">
            <button onClick={togglePlay} className="hover:text-indigo-400 transition-colors">
              {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
            </button>
            
            <button onClick={() => skipTime(-10)} className="hover:text-indigo-400 transition-colors" title="Rewind 10s">
              <RotateCcw className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2 group/volume relative">
              <button onClick={toggleMute} className="hover:text-indigo-400 transition-colors">
                {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className={`overflow-hidden accent-indigo-500 h-1 cursor-pointer transition-all duration-300 ${
                  canHover ? 'w-0 group-hover/volume:w-20' : 'w-20'
                }`}
              />
            </div>

            <span className="whitespace-nowrap text-xs font-medium tracking-wide sm:text-sm">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="relative flex items-center gap-3 sm:gap-4">
            <button onClick={toggleSubtitles} className={`transition-colors ${subtitlesEnabled ? 'text-indigo-400' : 'text-white/70 hover:text-white'}`} title="Subtitles (CC)">
              <Captions className="w-5 h-5" />
            </button>
            {supportsPictureInPicture && (
              <button onClick={togglePictureInPicture} className={`transition-colors ${isPictureInPicture ? 'text-indigo-400' : 'text-white/70 hover:text-white'}`} title="Picture in Picture">
                <PictureInPicture2 className="w-5 h-5" />
              </button>
            )}
            
            <div className="relative">
              <button 
                onClick={() => setShowSettings(!showSettings)} 
                className={`hover:text-indigo-400 transition-colors ${showSettings ? 'text-indigo-400 rotate-45' : ''} duration-300`}
                title="Settings"
              >
                <Settings className="w-5 h-5" />
              </button>
              
              {/* Settings Menu */}
              {showSettings && (
                <div className="absolute bottom-full right-0 mb-4 bg-gray-900/95 backdrop-blur border border-white/10 rounded-xl overflow-hidden min-w-[150px] shadow-2xl py-2 animate-in fade-in slide-in-from-bottom-2">
                  <div className="px-3 py-2 text-xs font-semibold text-white/50 border-b border-white/10 uppercase tracking-wider">
                    Playback Speed
                  </div>
                  {PLAYBACK_RATES.map((rate) => (
                    <button
                      key={rate}
                      onClick={() => changePlaybackRate(rate)}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors hover:bg-white/10 flex items-center justify-between ${
                        playbackRate === rate ? 'text-indigo-400 font-medium bg-indigo-500/10' : 'text-white'
                      }`}
                    >
                      {rate === 1 ? 'Normal' : `${rate}x`}
                      {playbackRate === rate && <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button onClick={toggleFullscreen} className="hover:text-indigo-400 transition-colors">
              {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>
      
      {/* Global CSS for VTT styling - injecting a subtle style to make standard captions look nicer */}
      <style dangerouslySetInnerHTML={{__html: `
        ::cue {
          background-color: rgba(0, 0, 0, 0.7);
          color: white;
          font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          font-weight: 500;
          font-size: 1.25rem;
          padding: 4px 8px;
          border-radius: 4px;
        }
      `}} />
    </div>
  );
}
