"""Certificate + hostname verified HTTPS for an ESP32 PPP data connection.

Supports only an exact pinned origin and /api/v1/ paths; no redirects,
no HTTP fallback, no trust-all SSL. No raw credential/HTTP payload logging.
"""
import json

class TransportError(Exception):
    pass

def load_cloud_profile(path="/blueguard-cloud.json"):
    try:
        with open(path) as f:
            profile=json.load(f)
    except (OSError,ValueError):
        raise TransportError("Cloud TLS profile is missing/invalid") from None
    if not isinstance(profile,dict) or set(profile)!={"schema","host","caDerPath"} or profile["schema"]!=1:
        raise TransportError("Unsupported cloud TLS profile")
    host=profile["host"]
    root=profile["caDerPath"]
    if not isinstance(host,str) or len(host)>180 or not host or not all(
        c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in host
    ) or host.startswith(".") or "." not in host or not isinstance(root,str) or not root.startswith("/"):
        raise TransportError("Invalid cloud host/CA file")
    if ".." in root or len(root)>96 or not root.endswith(".der"):
        raise TransportError("Unsafe CA certificate location")
    return profile

def _write_all(stream,data):
    offset=0
    while offset<len(data):
        amount=stream.write(data[offset:])
        if amount is None or amount<=0:
            raise TransportError("HTTPS write failed")
        offset+=amount

def _read_some(stream,limit):
    chunk=stream.read(limit)
    if not chunk:
        raise TransportError("HTTPS response ended unexpectedly")
    return chunk

def _read_chunked(stream,buf,limit):
    output=b""
    while True:
        while b"\r\n" not in buf:
            buf+=_read_some(stream,256)
            if len(buf)>limit+256:
                raise TransportError("Chunked response too large")
        size_text,buf=buf.split(b"\r\n",1)
        try:
            size=int(size_text.split(b";",1)[0],16)
        except ValueError:
            raise TransportError("Invalid chunk length") from None
        if size<0 or size+len(output)>limit:
            raise TransportError("Chunked response too large")
        while len(buf)<size+2:
            buf+=_read_some(stream,min(1024,size+2-len(buf)))
        if buf[size:size+2]!=b"\r\n":
            raise TransportError("Malformed chunk delimiter")
        output+=buf[:size]
        buf=buf[size+2:]
        if size==0:
            return output


class VerifiedHttpsTransport:
    def __init__(self,host,ca_der,net_socket,tls_module, max_response=8192):
        if not isinstance(host,str) or "." not in host or not host.replace(".","").replace("-","").isalnum():
            raise TransportError("Invalid API hostname")
        if not isinstance(ca_der,bytes) or len(ca_der)<100 or len(ca_der)>8192:
            raise TransportError("Trusted CA DER is required")
        self.host=host
        self.ca_der=ca_der
        self.socket=net_socket
        self.tls=tls_module
        self.max_response=max_response

    def request(self,method,path,headers,payload):
        if method not in ("GET","POST") or not isinstance(path,str) or not path.startswith("/api/v1/") or not all(
            c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-" for c in path):
            raise ValueError("Unsupported API path")
        for name,value in headers.items():
            if not isinstance(name,str) or not isinstance(value,str) or not name or "\r" in value or "\n" in value:
                raise ValueError("Invalid request header")
        data=(json.dumps(payload,separators=(",",":")).encode() if method=="POST" else b"")
        if len(data)>4096:
            raise ValueError("Payload is too large")
        # Mandatory validation: no feature detection fallback to CERT_NONE.
        ctx=self.tls.SSLContext(self.tls.PROTOCOL_TLS_CLIENT)
        ctx.verify_mode=self.tls.CERT_REQUIRED
        if ctx.verify_mode!=self.tls.CERT_REQUIRED:
            raise TransportError("TLS verification unavailable")
        ctx.load_verify_locations(cadata=self.ca_der)
        addresses=self.socket.getaddrinfo(self.host,443,0,self.socket.SOCK_STREAM)
        if not addresses:
            raise TransportError("API DNS failed")
        sock=None
        wrapped=None
        try:
            address=addresses[0]
            sock=self.socket.socket(address[0],address[1],address[2])
            sock.settimeout(18)
            sock.connect(address[-1])
            wrapped=ctx.wrap_socket(sock,server_hostname=self.host)
            request=("{} {} HTTP/1.1\r\nHost: {}\r\nAccept: application/json\r\n"
                     "Connection: close\r\nContent-Type: application/json\r\n"
                     "Content-Length: {}\r\n".format(method,path,self.host,len(data)))
            for key,value in headers.items():
                if not key or not all(c.isalnum() or c=="-" for c in key):
                    raise ValueError("Invalid header name")
                request+="{}: {}\r\n".format(key,value)
            _write_all(wrapped,request.encode()+b"\r\n"+data)
            received=b""
            while b"\r\n\r\n" not in received:
                received+=_read_some(wrapped,256)
                if len(received)>1800:
                    raise TransportError("Oversized API response headers")
            raw_headers,body=received.split(b"\r\n\r\n",1)
            lines=raw_headers.decode("ascii").split("\r\n")
            first=lines[0].split(" ")
            if len(first)<2 or not first[0].startswith("HTTP/1."):
                raise TransportError("Unsupported API response")
            code=int(first[1])
            if code in (301,302,303,307,308):
                raise TransportError("HTTPS redirect is prohibited")
            response_headers={}
            for line in lines[1:]:
                if ":" not in line:
                    raise TransportError("Malformed HTTPS headers")
                key,value=line.split(":",1)
                key=key.strip().lower()
                if key in response_headers:
                    raise TransportError("Duplicate HTTP header")
                response_headers[key]=value.strip()
            if response_headers.get("transfer-encoding")=="chunked":
                body=_read_chunked(wrapped,body,self.max_response)
            else:
                if "transfer-encoding" in response_headers:
                    raise TransportError("Unsupported transfer encoding")
                if "content-length" not in response_headers:
                    raise TransportError("Unknown HTTPS response length")
                length=int(response_headers["content-length"])
                if length<0 or length>self.max_response:
                    raise TransportError("HTTPS response too large")
                while len(body)<length:
                    body+=_read_some(wrapped,min(1024,length-len(body)))
                if len(body)!=length:
                    raise TransportError("HTTPS body length mismatch")
            result=json.loads(body.decode()) if body else {}
            if not isinstance(result,dict):
                raise TransportError("Unexpected API JSON")
            return {"status":code,"body":result,"code":result.get("code")}
        except TransportError:
            raise
        except Exception:
            # Includes TLS/hostname rejection, DNS and unexpected EOF.
            raise TransportError("Authenticated HTTPS request failed") from None
        finally:
            if wrapped is not None:
                try:wrapped.close()
                except Exception:pass
            elif sock is not None:
                try:sock.close()
                except Exception:pass

def create_verified_transport(profile):
    import socket
    import ssl
    with open(profile["caDerPath"],"rb") as f:
        ca=f.read(8193)
    return VerifiedHttpsTransport(profile["host"],ca,socket,ssl)
