"""Company URL checks at provider boundary; fixed API hosts never follow redirects."""
import ipaddress
import socket
from .core import public_url,Blocked


def research_url(url,resolver=socket.getaddrinfo):
    public_url(url)
    from urllib.parse import urlsplit
    host=urlsplit(url).hostname.rstrip('.')
    try:
        addresses=resolver(host,443,type=socket.SOCK_STREAM)
    except OSError:
        raise Blocked('Company hostname could not be safely resolved') from None
    if not addresses or any((not ipaddress.ip_address(r[4][0]).is_global or ipaddress.ip_address(r[4][0]).is_multicast) for r in addresses):
        raise Blocked('Company URL resolves to a nonpublic address')
    return host
