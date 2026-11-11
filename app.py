"""Local-only metadata diagnostic worker. Not publicly exposed."""
import os
import hmac
import secrets
import tempfile
import threading
import shutil
from pathlib import Path
from flask import send_file, after_this_request
import yt_dlp
from flask import Flask, request, jsonify
app=Flask(__name__)
BUSY=threading.Lock()
MAX_SECONDS=1800
import imageio_ffmpeg
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
TOKEN=os.environ.get('VEVEMP3_LOCAL_WORKER_TOKEN','')
@app.get('/healthz')
def health():
    return jsonify(ok=True,worker='local',yt_dlp=yt_dlp.version.__version__)
@app.post('/info')
def info():
    if not TOKEN or not hmac.compare_digest(request.headers.get('X-Worker-Token',''),TOKEN):
        return jsonify(error='Unauthorized'),403
    data=request.get_json(silent=True) or {}
    url=str(data.get('url',''))
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or (parsed.hostname or '').lower() not in ('youtube.com','www.youtube.com','youtu.be','m.youtube.com'):
        return jsonify(error='Invalid YouTube URL'),400
    try:
        with yt_dlp.YoutubeDL({'quiet':True,'skip_download':True,'noplaylist':True,'socket_timeout':12,'js_runtimes':{'node':{}}}) as ydl:
            meta=ydl.extract_info(url,download=False)
        return jsonify(title=meta.get('title'),duration=meta.get('duration'),id=meta.get('id'))
    except Exception:
        return jsonify(error='Media metadata unavailable'),502
@app.post('/convert')
def convert():
    if not TOKEN or not hmac.compare_digest(request.headers.get('X-Worker-Token',''),TOKEN):
        return jsonify(error='Unauthorized'),403
    data=request.get_json(silent=True) or {}
    url=str(data.get('url',''))
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or (parsed.hostname or '').lower() not in ('youtube.com','www.youtube.com','youtu.be','m.youtube.com'):
        return jsonify(error='Invalid YouTube URL'),400
    fmt=str(data.get('format','mp3')).lower()
    if fmt not in ('mp3','mp4'):
        return jsonify(error='Invalid format'),400
    if not BUSY.acquire(blocking=False):
        return jsonify(error='Worker busy'),429
    work=Path(tempfile.mkdtemp(prefix='vevemp3-local-'))
    try:
        opts={'quiet':True,'noplaylist':True,'socket_timeout':15,
              'outtmpl':str(work/'media.%(ext)s'),'max_filesize':300*1024*1024,
              'ffmpeg_location':FFMPEG,'js_runtimes':{'node':{}},'format':'bestaudio/best' if fmt=='mp3' else 'best[height<=720]/best'}
        if fmt=='mp3':
            opts['postprocessors']=[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]
        with yt_dlp.YoutubeDL(opts) as ydl:
            meta=ydl.extract_info(url,download=False)
            if (meta.get('duration') or 0)>MAX_SECONDS:
                return jsonify(error='Video too long'),400
            ydl.download([url])
        candidates=list(work.glob('*.mp3' if fmt=='mp3' else '*.mp4'))
        if not candidates:
            return jsonify(error='Conversion output missing'),502
        output=candidates[0]
        data_bytes=output.read_bytes()
        if len(data_bytes)>300*1024*1024:
            return jsonify(error='File too large'),413
        from io import BytesIO
        return send_file(BytesIO(data_bytes),mimetype='audio/mpeg' if fmt=='mp3' else 'video/mp4',
                         as_attachment=True,download_name='vevemp3.'+fmt)
    except Exception:
        return jsonify(error='Local conversion failed'),502
    finally:
        shutil.rmtree(work,ignore_errors=True)
        BUSY.release()

if __name__=='__main__':
    if not TOKEN:
        raise SystemExit('Set VEVEMP3_LOCAL_WORKER_TOKEN before starting')
    app.run(host='127.0.0.1',port=8765,debug=False)
