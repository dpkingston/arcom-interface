"""
Web server function of arcom-server
"""
import base64
import hashlib
import logging
import ssl

try:                 # Python 3
  from http.server import (SimpleHTTPRequestHandler)
  from socketserver import ThreadingMixIn
  from xmlrpc.server import (SimpleXMLRPCServer,
                             SimpleXMLRPCRequestHandler)
except ImportError:  # Python 2
  from SimpleHTTPServer import SimpleHTTPRequestHandler
  from SocketServer import ThreadingMixIn
  from SimpleXMLRPCServer import (SimpleXMLRPCServer,
                                  SimpleXMLRPCRequestHandler)

log = logging.getLogger('arcom')
PASSWD_FILE = 'arcom.passwd'


class BasicAuthorizor(object):
  """Implement validation for basic auth with cache."""
  def __init__(self):
    """Read in authorized hashs and store in memory."""
    self.valid_users = {}
    try:
      for line in open(PASSWD_FILE, "r"):
        user, password_hash = line.strip().split(':')
        self.valid_users[user] = password_hash
    except IOError, e:
      log.error('error processing %s: %s', PASSWD_FILE, e)
    
  def valid_auth(self, string):
    """Validate that user:hash is a valid credential."""
    authtype, value = string.split(' ')
    log.debug('Authenticating %s and "%s"', authtype, value)
    if authtype == 'Basic':
      value = base64.b64decode(value)
      user, password = value.split(':')
      password_hash = hashlib.sha224('arcom'+user+password).hexdigest()
      #log.debug('Authenticating %s with %s (%s)', user, password, hash1)
      if user in self.valid_users and self.valid_users[user] == password_hash:
        log.info('Login succeeded for %s', user)
        return True
    return False


authorizor = BasicAuthorizor()


class ArcomWebServer(ThreadingMixIn, SimpleXMLRPCServer):
  """Basic XMLRPC and GET server class with localhost only access."""
  def verify_request(self, request, client_address):
    host, port = client_address
    log.info('connection from %s:%s', host, port)
    return SimpleXMLRPCServer.verify_request(self, request, client_address)


class ArcomAuthorizingRequestHandler(SimpleHTTPRequestHandler,
                                     SimpleXMLRPCRequestHandler):
  """Add functionality to basic XMLRPC handler.
     We need to add authentication and handling of GETs.
     """
  rpc_paths = ('/RPC2')

  def __init__(self, *args, **kwargs):
    SimpleXMLRPCRequestHandler.__init__(self, *args, **kwargs)
    self.HTTPRequestHandler = SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)

  def do_AUTHHEAD(self):
    """Send authentication failure response."""
    log.debug('do AUTHHEAD')
    self.send_response(401)
    self.send_header('WWW-Authenticate', 'Basic realm=\"Arcom\"')
    self.send_header('Content-type', 'text/html')
    self.end_headers()

  def do_GET(self):
    """Add authentication to the XMLRPC handlers."""
    log.debug('do_GET: path %s', self.path)
    #print '  headers: %s' % self.headers
    if self.headers.getheader('Authorization') is None:
      log.debug('do_GET: No auth received')
      self.do_AUTHHEAD()
      self.wfile.write('No auth received')
    elif authorizor.valid_auth(self.headers.getheader('Authorization')):
      SimpleHTTPRequestHandler.do_GET(self)
    else:
      log.info('do_GET: invalid auth')
      self.do_AUTHHEAD()
      self.wfile.write('Not authenticated: ')
      self.wfile.write(self.headers.getheader('Authorization'))

  def do_POST(self):
    """Add authentication to the XMLRPC handlers."""
    log.debug('do_POST: path %s', self.path)
    log.debug('  content-length: %s', int(self.headers.getheader('content-length', 0)))
    #print '  headers: %s' % self.headers
    if self.headers.getheader('Authorization') is None:
      log.debug('do_POST: No auth received')
      self.do_AUTHHEAD()
      self.wfile.write('No auth received')
    elif authorizor.valid_auth(self.headers.getheader('Authorization')):
      SimpleXMLRPCRequestHandler.do_POST(self)
    else:
      log.info('do_POST: invalid auth')
      self.do_AUTHHEAD()
      self.wfile.write('Not authenticated: ')
      self.wfile.write(self.headers.getheader('Authorization'))


def run_server(arcom, opt):
  """Creat and run the core XMLRPC webserver."""
  server = ArcomWebServer(('', opt.port), ArcomAuthorizingRequestHandler, allow_none=True)
  server.socket = ssl.wrap_socket(
      server.socket,
      keyfile="key.pem",
      certfile='cert.pem',
      server_side=True)
  server.register_introspection_functions()
  arcom.register_functions(server)
  server.serve_forever()
