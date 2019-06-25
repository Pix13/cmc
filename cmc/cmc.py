#!/usr/bin/env python
# CoinMarketCap IRC Bot - Developed by acidvegas in Python (https://acid.vegas/cmc)

import http.client
import json
import random
import socket
import time

# Connection
server     = 'irc.server.com'
port	   = 6667
proxy      = None # Proxy should be a Socks5 in IP:PORT format.
use_ipv6   = False
use_ssl    = False
ssl_verify = False
vhost      = None
channel    = '#coin'
key        = None

# Certificate
cert_key  = None
cert_file = None
cert_pass = None

# Identity
nickname = 'CoinMarketCap'
username = 'cmc'
realname = 'acid.vegas/cmc'

# Login
nickserv_password = None
network_password  = None
operator_password = None

# Settings
throttle_cmd = 3
throttle_msg = 0.5
user_modes   = None

# Formatting Control Characters / Color Codes
bold        = '\x02'
italic      = '\x1D'
underline   = '\x1F'
reverse     = '\x16'
reset       = '\x0f'
white       = '00'
black       = '01'
blue        = '02'
green       = '03'
red         = '04'
brown       = '05'
purple      = '06'
orange      = '07'
yellow      = '08'
light_green = '09'
cyan        = '10'
light_cyan  = '11'
light_blue  = '12'
pink        = '13'
grey        = '14'
light_grey  = '15'

def coin_info(data):
	sep      = color('|', grey)
	sep2     = color('/', grey)
	rank     = color(data['rank'], pink)
	name     = '{0} ({1})'.format(color(data['name'], white), data['symbol'])
	value    = condense_value(data['price'])
	perc_1h  = color('{:,.2f}%'.format(data['percent']['1h']), percent_color(data['percent']['1h']))
	perc_24h = color('{:,.2f}%'.format(data['percent']['24h']), percent_color(data['percent']['24h']))
	perc_7d  = color('{:,.2f}%'.format(data['percent']['7d']), percent_color(data['percent']['7d']))
	percent  = sep2.join((perc_1h,perc_24h,perc_7d))
	volume   = '{0} {1}'.format(color('Volume:', white), '${:,}'.format(data['volume']))
	cap      = '{0} {1}'.format(color('Market Cap:', white), '${:,}'.format(data['market_cap']))
	return f'[{rank}] {name} {sep} {value} ({percent}) {sep} {volume} {sep} {cap}'

def coin_matrix(data): # very retarded way of calculating the longest strings per-column
	results = {'symbol':list(),'value':list(),'perc_1h':list(),'perc_24h':list(),'perc_7d':list(),'volume':list(),'cap':list()}
	for item in data:
		results['symbol'].append(item['symbol'])
		results['value'].append(condense_value(item['price']))
		for perc in ('1h','24h','7d'):
			results['perc_' + perc].append('{:,.2f}%'.format(item['percent'][perc]))
		results['volume'].append('${:,}'.format(item['volume']))
		results['cap'].append('${:,}'.format(item['market_cap']))
	for item in results:
		results[item] = len(max(results[item], key=len))
	if results['symbol'] < len('Symbol'):
		results['symbol'] = len('Symbol')
	if results['value'] < len('Value'):
		results['value'] = len('Value')
	if results['volume'] < len('Volume'):
		results['volume'] = len('Volume')
	if results['cap'] < len('Market Cap'):
		results['cap'] = len('Market Cap')
	return results

def coin_table(data):
	matrix = coin_matrix(data)
	header = color(' {0}   {1}   {2} {3} {4}   {5}   {6} '.format('Symbol'.center(matrix['symbol']), 'Value'.center(matrix['value']), '1H'.center(matrix['perc_1h']), '24H'.center(matrix['perc_24h']), '7D'.center(matrix['perc_7d']), 'Volume'.center(matrix['volume']), 'Market Cap'.center(matrix['cap'])), black, light_grey)
	lines  = [header,]
	for item in data:
		symbol   = item['symbol'].ljust(matrix['symbol'])
		value    = condense_value(item['price']).rjust(matrix['value'])
		perc_1h  = color('{:,.2f}%'.format(item['percent']['1h']).rjust(matrix['perc_1h']),   percent_color(item['percent']['1h']))
		perc_24h = color('{:,.2f}%'.format(item['percent']['24h']).rjust(matrix['perc_24h']), percent_color(item['percent']['24h']))
		perc_7d  = color('{:,.2f}%'.format(item['percent']['7d']).rjust(matrix['perc_7d']),   percent_color(item['percent']['7d']))
		volume   = '${:,}'.format(item['volume']).rjust(matrix['volume'])
		cap      = '${:,}'.format(item['market_cap']).rjust(matrix['cap'])
		lines.append(' {0} | {1} | {2} {3} {4} | {5} | {6} '.format(symbol,value,perc_1h,perc_24h,perc_7d,volume,cap))
	return lines

def color(msg, foreground, background=None):
	return f'\x03{foreground},{background}{msg}{reset}' if background else f'\x03{foreground}{msg}{reset}'

def condense_value(value):
	return '${0:,.8f}'.format(value) if value < 0.01 else '${0:,.2f}'.format(value) if value < 24.99 else '${:,}'.format(int(value))

def debug(msg):
	print(f'{get_time()} | [~] - {msg}')

def error(msg, reason=None):
	print(f'{get_time()} | [!] - {msg} ({reason})') if reason else print(f'{get_time()} | [!] - {msg}')

def error_exit(msg):
	raise SystemExit(f'{get_time()} | [!] - {msg}')

def get_float(data):
	try:
		float(data)
		return True
	except ValueError:
		return False

def get_time():
	return time.strftime('%I:%M:%S')

def percent_color(percent):
	if percent == 0.0:
		return grey
	elif percent < 0.0:
		return brown if percent > -10.0 else red
	else:
		return green if percent < 10.0 else light_green

class CoinMarketCap(object):
	def __init__(self):
		self.cache = {'global':{'last_updated':0},'ticker':{'BTC':{'last_updated':0}}}

	def _global(self):
		if time.time() - self.cache['global']['last_updated'] < 300:
			return self.cache['global']
		else:
			conn = http.client.HTTPSConnection('api.coinmarketcap.com', timeout=15)
			conn.request('GET', '/v2/global/')
			data = json.loads(conn.getresponse().read())['data']
			conn.close()
			results = {
				'cryptocurrencies' : data['active_cryptocurrencies'],
				'markets'          : data['active_markets'],
				'btc_dominance'    : int(data['bitcoin_percentage_of_market_cap']),
				'market_cap'       : int(data['quotes']['USD']['total_market_cap']),
				'volume'           : int(data['quotes']['USD']['total_volume_24h']),
				'last_updated'     : int(data['last_updated'])
			}
			self.cache['global'] = results
			return results

	def _ticker(self):
		if time.time() - self.cache['ticker']['BTC']['last_updated'] < 300:
			return self.cache['ticker']
		else:
			self.cache['ticker'] = dict()
			for i in range(1,int(self._global()['cryptocurrencies']/100)+2):
				conn = http.client.HTTPSConnection('api.coinmarketcap.com', timeout=15)
				conn.request('GET', '/v2/ticker/?start=' + str(((i*100)-100)+1))
				data = json.loads(conn.getresponse().read().replace(b': null', b': "0"'))['data']
				conn.close()
				for item in data:
					results = dict()
					del data[item]['id'], data[item]['website_slug'], data[item]['circulating_supply'], data[item]['total_supply'], data[item]['max_supply']
					self.cache['ticker'][data[item]['symbol']] = {
						'name'         : data[item]['name'],
						'symbol'       : data[item]['symbol'],
						'rank'         : data[item]['rank'],
						'price'        : float(data[item]['quotes']['USD']['price']),
						'volume'       : int(data[item]['quotes']['USD']['volume_24h']),
						'market_cap'   : int(data[item]['quotes']['USD']['market_cap']),
						'percent'      : {'1h':float(data[item]['quotes']['USD']['percent_change_1h']),'24h':float(data[item]['quotes']['USD']['percent_change_24h']),'7d':float(data[item]['quotes']['USD']['percent_change_7d'])},
						'last_updated' : int(data[item]['last_updated'])
					}
					data[item] = None
			return self.cache['ticker']

class IRC(object):
	def __init__(self):
		self.last = 0
		self.slow = False
		self.sock = None

	def connect(self):
		try:
			self.create_socket()
			self.sock.connect((server, port))
			self.register()
		except socket.error as ex:
			error('Failed to connect to IRC server.', ex)
			self.event_disconnect()
		else:
			self.listen()

	def create_socket(self):
		family = socket.AF_INET6 if use_ipv6 else socket.AF_INET
		if proxy:
			proxy_server, proxy_port = proxy.split(':')
			self.sock = socks.socksocket(family, socket.SOCK_STREAM)
			self.sock.setblocking(0)
			self.sock.settimeout(15)
			self.sock.setproxy(socks.PROXY_TYPE_SOCKS5, proxy_server, int(proxy_port))
		else:
			self.sock = socket.socket(family, socket.SOCK_STREAM)
		if vhost:
			self.sock.bind((vhost, 0))
		if use_ssl:
			ctx = ssl.SSLContext()
			if cert_file:
				ctx.load_cert_chain(cert_file, cert_key, cert_pass)
			if ssl_verify:
				ctx.verify_mode = ssl.CERT_REQUIRED
				ctx.load_default_certs()
			else:
				ctx.check_hostname = False
				ctx.verify_mode = ssl.CERT_NONE
			self.sock = ctx.wrap_socket(self.sock)

	def error(self, chan, msg, reason=None):
		if reason:
			self.sendmsg(chan, '[{0}] {1} {2}'.format(color('!', red), msg, color('({0})'.format(reason), grey)))
		else:
			self.sendmsg(chan, '[{0}] {1}'.format(color('!', red), msg))

	def event_connect(self):
		if user_modes:
			self.raw('MODE {nickname} +{user_modes}')
		if nickserv_password:
			self.sendmsg('NickServ', f'IDENTIFY {nickname} {nickserv_password}')
		if operator_password:
			self.raw(f'OPER {username} {operator_password}')
		self.join_channel(channel, key)

	def event_disconnect(self):
		self.sock.close()
		time.sleep(10)
		self.connect()

	def event_kick(self, chan, kicked):
		if chan == channel and kicked == nickname:
			time.sleep(3)
			self.join_channel(channel, key)

	def event_message(self, nick, chan, msg):
		try:
			if msg[:1] in '!@$':
				if time.time() - self.last < throttle_cmd:
					if not self.slow:
						self.error(chan, 'Slow down nerd!')
						self.slow = True
				else:
					self.slow = False
					args = msg.split()
					if msg == '@cmc':
						self.sendmsg(chan, bold + 'CoinMarketCap IRC Bot - Developed by acidvegas in Python - https://acid.vegas/cmc')
					elif msg.startswith('$') and len(args) == 1:
						msg = msg.upper()
						if ',' in msg:
							coins = list(msg[1:].split(','))[:10]
							data = [CMC._ticker()[coin] for coin in coins if coin in CMC._ticker()]
							if len(data) == 1:
								coin = data[0]
								self.sendmsg(chan, coin_info(coin))
							elif len(data) > 1:
								for line in coin_table(data):
									self.sendmsg(chan, line)
							else:
								self.error(chan, 'Invalid cryptocurrency names!')
						else:
							coin = msg[1:]
							if not coin.isdigit():
								if coin in CMC._ticker():
									self.sendmsg(chan, coin_info(CMC._ticker()[coin]))
								else:
									self.error(chan, 'Invalid cryptocurrency name!')
					elif args[0] == '!search' and len(args) >= 2:
						query = msg[8:]
						ticker_data = CMC._ticker()
						coins = [ticker_data[coin] for coin in ticker_data if query.lower() in ticker_data[coin]['name'].lower() or query.lower() in ticker_data[coin]['symbol'].lower()][:10]
						if coins:
							for coin in coins:
								self.sendmsg(chan, '[{0}] {1} {2}'.format(color(str(coins.index(coin)+1).zfill(2), pink), coin['name'], color('({0})'.format(coin['symbol']), grey)))
						else:
							self.error(chan, 'No results found.')
					elif msg == '!stats':
						global_data = CMC._global()
						self.sendmsg(chan, '{0}{1}{2} {3:,}'.format(bold, 'Cryptocurrencies :', reset, global_data['cryptocurrencies']))
						self.sendmsg(chan, '{0}{1}{2} {3:,}'.format(bold, 'Markets          :', reset, global_data['markets']))
						self.sendmsg(chan, '{0}{1}{2} {3}%'.format(bold, 'BTC Dominance    :', reset, global_data['btc_dominance']))
						self.sendmsg(chan, '{0}{1}{2} ${3:,}'.format(bold, 'Market Cap       :', reset, global_data['market_cap']))
						self.sendmsg(chan, '{0}{1}{2} ${3:,}'.format(bold, 'Volume           :', reset, global_data['volume']))
					elif msg == '!top':
						data = list(CMC._ticker().values())[:10]
						for line in coin_table(data):
							self.sendmsg(chan, line)
					elif args[0] in ('!bottom','!top') and len(args) == 2:
						option = args[1].lower()
						if option in ('1h','24h','7d','value','volume'):
							data = {}
							ticker_data = CMC._ticker()
							for item in ticker_data:
								if option in ('1h','24h','7d'):
									data[item] = ticker_data[item]['percent'][option]
								elif option == 'value':
									data[item] = ticker_data[item]['price']
								else:
									data[item] = ticker_data[item]['volume']
							if args[0] == '!bottom':
								sorted_data = sorted(data, key=data.get, reverse=False)[:10]
								data = [ticker_data[coin] for coin in sorted_data]
							else:
								sorted_data = sorted(data, key=data.get, reverse=False)[-10:]
								data = [ticker_data[coin] for coin in sorted_data][::-1]
							for line in coin_table(data):
								self.sendmsg(chan, line)
						else:
							self.error(chan, 'Invalid option!', 'Valid options are 1h, 24h, 7d, value, & volume')
				self.last = time.time()
		except Exception as ex:
			self.error(chan, 'Unknown error occured!', ex)

	def handle_events(self, data):
		args = data.split()
		if args[0] == 'PING':
			self.raw('PONG ' + args[1][1:])
		elif args[1] == '001':
			self.event_connect()
		elif args[1] == '433':
			self.raw('NICK CMC_' + str(random.randint(10,99)))
		elif args[1] == 'KICK' and len(args) >= 4:
			nick   = args[0].split('!')[0][1:]
			chan   = args[2]
			kicked = args[3]
			self.event_kick(nick, chan, kicked)
		elif args[1] == 'PRIVMSG' and len(args) >= 4:
			nick = args[0].split('!')[0][1:]
			chan = args[2]
			msg  = ' '.join(args[3:])[1:]
			if chan == channel:
				self.event_message(nick, chan, msg)

	def join_channel(self, chan, key=None):
		self.raw(f'JOIN {chan} {key}') if key else self.raw('JOIN ' + chan)

	def listen(self):
		while True:
			try:
				data = self.sock.recv(1024).decode('utf-8')
				for line in (line for line in data.split('\r\n') if len(line.split()) >= 2):
					debug(line)
					self.handle_events(line)
			except (UnicodeDecodeError,UnicodeEncodeError):
				pass
			except Exception as ex:
				error('Unexpected error occured.', ex)
				break
		self.event_disconnect()

	def raw(self, msg):
		self.sock.send(bytes(msg + '\r\n', 'utf-8'))

	def register(self):
		if network_password:
			self.raw('PASS ' + network_password)
		self.raw(f'USER {username} 0 * :{realname}')
		self.raw('NICK ' + nickname)

	def sendmsg(self, target, msg):
		self.raw(f'PRIVMSG {target} :{msg}')
		time.sleep(throttle_msg)

# Main
if proxy:
	try:
		import socks
	except ImportError:
		error_exit('Missing PySocks module! (https://pypi.python.org/pypi/PySocks)')
if use_ssl:
	import ssl
CMC = CoinMarketCap()
IRC().connect()
