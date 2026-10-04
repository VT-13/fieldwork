"""Never log request payloads, provider bodies, tokens or student documents."""
import logging
import re
SENSITIVE=re.compile(r'token|secret|password|authorization|cookie|credential|api.?key|resume|body|raw',re.I)


def redact(value):
    if isinstance(value,dict):
        return {str(k):'[REDACTED]' if SENSITIVE.search(str(k)) else redact(v) for k,v in value.items()}
    if isinstance(value,tuple):return tuple(redact(v) for v in value)
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):
        value=re.sub(r'(?i)((?:cookie|authorization)\s*:\s*)[^\n]+',r'\1[REDACTED]',value)
        value=re.sub(r'(?i)(Bearer\s+)[^\s,;]+',r'\1[REDACTED]',value)
        value=re.sub(r'(?i)((?:access_token|refresh_token|api_key|password|secret|code|state)=)[^&\s]+',r'\1[REDACTED]',value)
        # Configured secret values can also occur in third-party exception strings.
        from .config import settings
        cfg=settings()
        for key in ('api_key','oauth_client_secret','oauth_refresh_token','credential_keys','operator_password_hash','openai_api_key','hunter_api_key','tavily_api_key','firecrawl_api_key','apollo_api_key','google_maps_api_key'):
            secret=getattr(cfg,key,'')
            if secret:value=value.replace(secret,'[REDACTED]')
        return value[:500]
    return value


class SafeLogFilter(logging.Filter):
    def filter(self,record):
        # No provider traceback locals or HTTP query/token dumps in persisted logs.
        record.msg=redact(record.msg);record.args=redact(record.args)
        record.msg=redact(record.getMessage());record.args=();record.exc_info=None;record.exc_text=None
        return True


def install_logging():
    for name in ('httpx','httpcore','openai','sqlalchemy.engine','sqlalchemy.pool','uvicorn.access'):
        logger=logging.getLogger(name);logger.disabled=True;logger.handlers=[logging.NullHandler()];logger.propagate=False
        for child in list(logging.Logger.manager.loggerDict):
            if child.startswith(name+'.'):logging.getLogger(child).disabled=True
    handlers=set(logging.getLogger().handlers)
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger,logging.Logger):handlers.update(logger.handlers)
    for handler in handlers:
        if not any(isinstance(f,SafeLogFilter) for f in handler.filters):handler.addFilter(SafeLogFilter())
