"""Local bounded JSONL query log; login fields and raw exception bodies are excluded."""
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
_lock = threading.Lock()
_logger = None


def scrub(value):
    text = str(value)
    if re.search(r'(?i)\b(parola\w*|şifre\w*|password|api[_ -]?key|token|secret|authorization)\b', text):
        return '[GİZLİ BİLGİ ALANI MASKELENDİ]'
    text = re.sub(r'(?i)\b(authorization\s*:\s*bearer)\s+\S+', r'\1 [GİZLENDİ]', text)
    text = re.sub(r'''(?ix)\b(parola\w*|şifre\w*|password|api[_ -]?key|token|secret)\s*[=:]\s*(?:"[^"]*"|'[^']*'|\S+)''', r'\1=[GİZLENDİ]', text)
    text = re.sub(r'(?i)\b(sk-[a-z0-9_-]{12,})\b', '[GİZLENDİ]', text)
    return text[:8000]


def record(question, result, elapsed, session, username=None):
    global _logger
    with _lock:
        if _logger is None:
            LOG_DIR.mkdir(exist_ok=True)
            _logger = logging.Logger('query_audit', level=logging.INFO)
            handler = RotatingFileHandler(LOG_DIR/'queries.jsonl', maxBytes=1024*1024, backupCount=4, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            # Disk hatasını arayüze bildir; kayıt kaybı sessiz kalmasın.
            def fail(rec): raise OSError('Yerel sorgu kaydı yazılamadı')
            handler.handleError = fail
            _logger.addHandler(handler)
    payload = {'time_utc':datetime.now(timezone.utc).isoformat(), 'request_id':str(uuid.uuid4()),
               'session_id':session, 'username':username, 'question':scrub(question), 'answer':scrub(result.get('answer','')),
               'channel':result.get('type'), 'seconds':round(elapsed,3),
               'error':result.get('type')=='ERROR',
               'sources':[{'source':scrub(s.get('source','')), 'section':scrub(s.get('section',''))}
                          for s in result.get('sources',[])[:12]]}
    _logger.info(json.dumps(payload, ensure_ascii=False))
