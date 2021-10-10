import argparse, sys, pandas, numpy, math, re, json
from pandas import DataFrame


def main():
	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawTextHelpFormatter,
		usage='%s [-c name=gp_value]... [-i|-r|-x tag]... source_files... [--csv|--txt|--html|--json output_file]' % sys.argv[0],
		description='''	
Creates a shop with items based on the provided tags using the provided currencies. If no tags are provided, then all items in item source files will be used.

Examples: 
	{name} ./DnD-5E-Items.csv ./My-Custom-Items.csv
Creates a store with all items in DnD-5E-Items.csv and My-Custom-Items.csv
	
	{name} -i weapons ./DnD-5E-Items.csv
Creates a store with all weapons in DnD-5E-Items.csv
	
	{name} -i armor -i weapons -i "adventuring gear" ./DnD-5E-Items.csv
Creates a store with all weapons, armor, and adventuring gear in DnD-5E-Items.csv
	
	{name} -i armor -i weapons -i "adventuring gear" -A -W ./DnD-5E-Items.csv
Same as above, but also shows the AC (-A) and weapon damage (-W)
	
	{name} -i armor -i weapons -i "adventuring gear" -x mounts -r metal -A -W ./DnD-5E-Items.csv
Same as above, but excludes mount-related items and only shows items tagged with "metal"
	
	{name} -c ep=0.5 -c bp=0.02 -i weapons -W ./DnD-5E-Items.csv
Creates a store with all weapons in DnD-5E-Items.csv, but adds electrum (ep) and brass (bp) coins as price options
	
	{name} --no-std -c ep=0.5 -c bp=0.02 -w kg=0.4545 -w g=0.0004545 -i weapons -W ./DnD-5E-Items.csv
Same as above, but removes the standard D&D units (gp, sp, cp coins and ton, lb., oz weights) and uses only electrum (ep) and brass (bp) coins and metric weights
		
'''.format(name=sys.argv[0]),
	)
	#
	parser.add_argument(
		'source_files',
		nargs='+',
		help='Source .csv files, which must have the columns: Name,Price (gp),Weight (lb.),Category,Properties,AC,Damage,Tags,Source'
	)
	## currency options
	parser.add_argument(
		'-c', '--currency', dest='currencies', action='append', nargs=1,
		type=currency_validator,
		help='add currency in format XX=#.# where XX is the currency label and #.# is the gold piece value (e.g. -c sp=0.1)'
	)
	parser.add_argument('--sigfigs', dest='sigfigs', type=int, default=1, help='required number of significant figures in custom currency calculation (eg 1 sig-fig will favor currencies whose prices are between 1 and 9, while 2 sig-figs favors 10-99), default: 1')
	parser.add_argument('-F', '--free', dest='free', action='store_true', default=False, help='allow items to have price == 0 (otherwise min price is 1 of lowest denomination currency)')
	## weight options
	parser.add_argument(
		'-w', '--weight', dest='weights', action='append', nargs=1,
		type=currency_validator,
		help='add weight unit in format XX=#.# where XX is the unit label and #.# is the pound value (e.g. -w kg=0.4545)'
	)
	parser.add_argument('-N', '--no-std', dest='nostd', action='store_true', default=False,
						help='do not use standard D&D prices and weight measures')
	## filter options
	parser.add_argument(
		'-i', '--include', dest='include', action='append', nargs=1, help='include items with this tag'
	)
	parser.add_argument(
		'-r', '--require', dest='require', action='append', nargs=1, help='all included items must have this tag'
	)
	parser.add_argument(
		'-x', '--exclude', dest='exclude', action='append', nargs=1, help='exclude items with this tag'
	)
	## display options
	parser.add_argument('-A', '--armor', dest='armor', action='store_true', default=False, help='show Armor Class values')
	parser.add_argument('-W', '--weapon', dest='weapons', action='store_true', default=False, help='show weapon damage values')
	## output options
	parser.add_argument('--csv', help='save created shop to specified .csv file')
	parser.add_argument('--txt', help='save created shop to specified .txt file (tab delimited)')
	parser.add_argument('--json', help='save created shop to specified file in json format')
	parser.add_argument('--html', help='save created shop to specified file in json format')
	#
	args = parser.parse_args()
	run(args)

def run(kwargs):
	# print('kwargs.source_files',kwargs.source_files)
	# print('kwargs.include',kwargs.include)
	# print('kwargs.require',kwargs.require)
	# print('kwargs.exclude',kwargs.exclude)
	# print('kwargs.currencies',kwargs.currencies)
	# print('kwargs.csv',kwargs.csv)
	# print('kwargs.json',kwargs.json)
	# print('kwargs.txt',kwargs.txt)
	# print('kwargs.html',kwargs.html)
	collection: DataFrame = None
	for src in kwargs.source_files:
		df = pandas.read_csv(src)
		if collection is None:
			collection = df
		else:
			collection.append(df)
	if kwargs.include is not None:
		collection = includeTags(collection, [x[0] for x in kwargs.include])
	if kwargs.require is not None:
		collection = requireTags(collection, [x[0] for x in kwargs.require])
	if kwargs.exclude is not None:
		collection = excludeTags(collection, [x[0] for x in kwargs.exclude])
	#
	weight_dict = {}
	if kwargs.nostd == False:
		weight_dict = {
			'ton':2000,
			'lb.':1,
			'oz':1/16
		}
	if kwargs.weights is not None:
		for w in kwargs.weights:
			s = w[0].split('=')
			xx = str(s[0]).strip()
			vv = float(str(s[1]).strip())
			weight_dict[xx] = vv
	currency_dict = {}
	if kwargs.nostd == False:
		currency_dict = {
			'gp':1,
			'sp':0.1,
			'cp':0.01,
		}
	if kwargs.currencies is not None:
		for c in kwargs.currencies:
			s = c[0].split('=')
			xx = str(s[0]).strip()
			vv = float(str(s[1]).strip())
			currency_dict[xx] = vv
	store = create_store(item_table=collection, currency_dict=currency_dict, weight_dict=weight_dict, kwargs=kwargs)
	print(output_ascii(store))
	if kwargs.csv is not None:
		save_csv(store, kwargs.csv)
	if kwargs.txt is not None:
		save_txt(store, kwargs.txt)
	if kwargs.html is not None:
		save_html(store, kwargs.html)
	if kwargs.json is not None:
		save_json(store, kwargs.json)

def save_csv(shop: DataFrame, fpath):
	if not str(fpath).lower().endswith('.csv'):
		fpath = str(fpath) + '.csv'
	shop.to_csv(fpath, index=False)

def save_txt(shop: DataFrame, fpath):
	if not str(fpath).lower().endswith('.txt'):
		fpath = str(fpath) + '.txt'
	shop.to_csv(fpath, index=False, sep='\t')

def save_json(shop: DataFrame, fpath):
	rows = []
	for i, row in shop.iterrows():
		d = {}
		for c in shop.columns:
			d[c] = row[c]
		rows.append(d)
	with open(fpath, 'w') as fout:
		json.dump(rows, fout, indent='\t')

def save_html(shop: DataFrame, fpath):
	html_str = '<html>\n<head>'
	html_str += '''<style>
table {
	border-collapse: collapse;
}
th, td {
	padding: 0.5em;
}
tr:nth-child(even) {
	background-color: Lightgray;
}
.Name {
	text-align: left;
}
.Price {
	text-align: right;
}
.Weight {
	text-align: right;
}
.AC {
	text-align: center;
}
.Damage {
	text-align: center;
}
.Properties {
	text-align: left;
}
.Category {
	text-align: center;
}
.Source {
	text-align: center;
}
</style>'''
	html_str += '</head>\n<body><table class="shoptable">\n'
	html_str += '\t<tr class="header">'
	for c in shop.columns:
		html_str += '<th class="%s">%s</th>' % (str(c).replace(' ',''), str(c).replace('<','&lt;').replace('>','&gt;').replace('&','&amp;'))
	html_str += '</tr>\n'
	for i, row in shop.iterrows():
		html_str += '\t<tr>'
		for c in shop.columns:
			n = str(row[c]).replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
			html_str += '<td class="%s">%s</td>' % (str(c).replace(' ',''), n)
		html_str += '</tr>\n'
	html_str += '</table></body></html>\n'
	with open(fpath, 'w') as fout:
		fout.write(html_str)

def create_store(item_table: DataFrame, currency_dict:{}=None, weight_dict:{}=None, kwargs={}) -> DataFrame:
	out_rows = []
	item_table.sort_values(by=['Category', 'Name'])
	columns = ['Name', 'Price (gp)', 'Weight (lb.)']
	if kwargs.armor:
		columns += ['AC']
	if kwargs.weapons:
		columns += ['Damage']
	if kwargs.armor or kwargs.weapons:
		columns += ['Properties']
	columns += ['Category', 'Source']
	out_columns = [x.replace('Price (gp)', 'Price').replace('Weight (lb.)', 'Weight') for x in columns]
	for i, row in item_table.iterrows():
		orow = []
		for col in columns:
			if col == 'Price (gp)':
				orow.append(to_currency(row[col], currency_dict=currency_dict, sigfigs=kwargs.sigfigs, nofree=(kwargs.free == False)))
			elif col == 'Weight (lb.)':
				orow.append(to_weight(row[col], weight_dict=weight_dict, sigfigs=kwargs.sigfigs))
			else:
				orow.append(format_entry(row[col]))
		out_rows.append(orow)
	return DataFrame(data=out_rows, columns=out_columns)

def output_ascii(store: DataFrame):
	string_out = ''
	col_widths = {
		'Name':20,
		'Price':10,
		'Weight':10,
		'AC':8,
		'Damage':16,
		'Properties':24,
		'Category':16,
		'Source':8
	}
	col_aligns = {
		'Name': 'left',
		'Price': 'right',
		'Weight': 'right',
		'AC': 'center',
		'Damage': 'center',
		'Properties': 'left',
		'Category': 'center',
		'Source': 'center'
	}
	widths = [col_widths[k] for k in store.columns]
	aligns = [col_aligns[k] for k in store.columns]
	string_out += string_box_row(store.columns, widths, ['center']*len(widths), v_align='bottom',
								 draw_top_line=True, draw_bottom_line=True)
	#
	for i, row in store.iterrows():
		string_out += string_box_row(row, widths, aligns, v_align='top',
								 draw_top_line=False, draw_bottom_line=True)
	return string_out

def string_box_row(texts, widths, h_alignments, v_align='top', draw_top_line=False, draw_bottom_line=False, h_delim='|', v_delim='-', x_delim='+'):
	if not (v_align == 'top' or v_align == 'bottom'): raise KeyError('Vertical alignment %s not supported' % v_align)
	if len(texts) != len(widths) or len(widths) != len(h_alignments):
		raise KeyError('length of texts, widths, and h_alignments lists must be equal')
	boxes = []
	num_rows = 1
	for i in range(0, len(texts)):
		sbox = string_box(text=texts[i], w=widths[i], align=h_alignments[i])
		boxes.append(sbox)
		if len(sbox) > num_rows:
			num_rows = len(sbox)
	row_boxes = []
	if v_align == 'top':
		for i in range(0, len(boxes)):
			b = boxes[i]
			while len(b) < num_rows:
				b = b + [pad('', w=widths[i], align=h_alignments[i])]
			row_boxes.append(b)
	elif v_align == 'bottom':
		for i in range(0, len(boxes)):
			b = boxes[i]
			while len(b) < num_rows:
				b = [pad('', w=widths[i], align=h_alignments[i])] + b
			row_boxes.append(b)
	str_out = ''
	if draw_top_line:
		str_out += x_delim
		for w in widths:
			str_out += v_delim*int(w)
			str_out += x_delim
		str_out += '\n'
	for r in range(0, num_rows):
		str_out += h_delim
		for c in range(0, len(row_boxes)):
			str_out += row_boxes[c][r]
			str_out += h_delim
		str_out += '\n'
	if draw_bottom_line:
		str_out += x_delim
		for w in widths:
			str_out += v_delim*int(w)
			str_out += x_delim
		str_out += '\n'
	return str_out

def string_box(text: str, w: int, align='left') -> []:
	# returns lines
	text = text.strip()
	if not (align == 'left' or align == 'right' or align == 'center'): raise KeyError('Alignment %s not supported' % align)
	if len(text) <= w: return [pad(text, w, align)]
	lines = []
	match_expr = '.{1,'+str(int(w))+'}\\s'
	while len(text) > 0:
		chunk = re.match(match_expr, text)
		if len(text) <= w:
			lines.append(pad(text, w, align))
			break
		elif chunk is None:
			## first word is too long
			lines.append(pad(text[0:w-1]+'-', w, align))
			text = text[w-1:].strip()
		else:
			lines.append(pad(chunk[0].strip(), w, align))
			text = text[len(chunk[0]):].strip()
	return lines

def pad(text: str, w: int, align='left'):
	if align == 'left':
		return text + ' '*(w - len(text))
	elif align == 'right':
		return ' ' * (w - len(text)) + text
	elif align == 'center':
		n: int = (w - len(text))
		return ' ' * (n-(n//2)) + text + ' ' * (n//2)
	raise KeyError('Alignment %s not supported' % align)


def to_currency(src_price, currency_dict: {}=None, sigfigs:int=2, nofree=True):
	src_price = float(src_price)
	default_fmt_str = '%.'+str(int(sigfigs))+'f'
	if currency_dict is None or len(currency_dict) == 0:
		# no currencies specified, use raw price
		return default_fmt_str % src_price
	else:
		# find highest value currency with given sigfigs integer value
		prices = {}; int_key_list = []
		for c in currency_dict:
			p = src_price / currency_dict[c]
			prices[c] = p
			int_key_list.append((int(p), c))
		int_key_list.sort() ## sorts from fewest to most coins
		sigfig_list = [int_digits(x[0]) for x in int_key_list]
		i = 0
		while i < len(int_key_list) - 1:
			if sigfig_list[i] >= sigfigs:
				break
			i += 1
		num_coins = int_key_list[i][0]
		coin_label = int_key_list[i][1]
		if num_coins <= 0:
			# pick smallest denomination
			denom_key_list = [(currency_dict[k], k) for k in currency_dict]
			denom_key_list.sort()  # sort by lowest to highest values
			coin_label = denom_key_list[0][1]
			if nofree == True and num_coins <= 0:
				### no free lunch!
				num_coins = 1
		#return ('[%s] => ' % src_price)+str(num_coins) + ' ' + str(coin_label)
		return format_number(num_coins, sigfigs=sigfigs) + ' ' + str(coin_label)

def to_weight(src_weight, weight_dict: {}=None, sigfigs:int=2):
	src_weight = float(src_weight)
	default_fmt_str = '%.'+str(int(sigfigs))+'f'
	if weight_dict is None or len(weight_dict) == 0:
		# no currencies specified, use raw price
		return default_fmt_str % src_weight
	else:
		# find highest value with given sigfigs integer value
		weights = {}; int_key_list = []
		for c in weight_dict:
			w = src_weight / weight_dict[c]
			weights[c] = w
			int_key_list.append((int(w), c))
		int_key_list.sort() ## sorts from fewest to most coins
		sigfig_list = [int_digits(x[0]) for x in int_key_list]
		i = 0
		while i < len(int_key_list) - 1:
			if sigfig_list[i] >= sigfigs:
				break
			i += 1
		num_w = int_key_list[i][0]
		w_label = int_key_list[i][1]
		if num_w <= 0:
			# pick smallest denomination
			u_key_list = [(weight_dict[k], k) for k in weight_dict]
			u_key_list.sort()  # sort by lowest to highest values
			w_label = u_key_list[0][1]
		#return ('[%s] => ' % src_price)+str(num_coins) + ' ' + str(coin_label)
		return format_number(num_w, sigfigs=sigfigs) + ' ' + str(w_label)

def currency_validator(arg_str):
	split = str(arg_str).split('=')
	if len(split) != 2:
		raise argparse.ArgumentTypeError('Invalid currency argument: "%s". Must be in format XX=#' % arg_str)
	try:
		v = float(split[1].strip())
	except:
		raise argparse.ArgumentTypeError('Invalid currency argument: "%s". Value must be a decimal number' % arg_str)
	return arg_str

def format_number(x, sigfigs: int) -> str:
	#digits = int_digits(x)
	sf = '%i' % (sigfigs)
	if x >= 1e15:
		expr = '%.'+sf+'E'
		return expr % x
	elif x >= 1e12:
		expr = '%.' + sf + 'fT'
		return expr % (x / 1e12)
	elif x >= 1e9:
		expr = '%.' + sf + 'fB'
		return expr % (x / 1e9)
	elif x >= 1e6:
		expr = '%.' + sf + 'fM'
		return expr % (x / 1e6)
	elif x >= 10000:
		expr = '%.' + sf + 'fK'
		return expr % (x / 1000)
	elif x >= 1000:
		return add_int_commas(int(x))
	#
	if int(x) == x:
		return '%i' % x
	else:
		expr = '%.' + str(sigfigs) + 'f'
		return expr % x
def add_int_commas(x: int):
	x = str(x)
	xx = ''
	for i in range(0, len(x)):
		r = len(x) - i
		if i > 0 and r % 3 == 0:
			xx += ','
		xx += x[i]
	return xx
def int_digits(x) -> int:
	if x is None:
		return 0
	elif type(x) != float:
		try:
			x = float(x)
		except:
			return 0
	elif numpy.isnan(x):
		return 0
	if x == 0: return 0
	if x >= 1:
		return int(math.log10(abs(x))+1)
	else:
		return int(math.log10(abs(x)))

def includeTags(df: DataFrame, tags: []) -> DataFrame:
	out_rows = []
	for i, row in df.iterrows():
		item_tags = [str(t).lower() for t in str(row['Tags']).strip().split(';')]
		for t in [str(t).lower() for t in tags]:
			if t in item_tags:
				out_rows.append(row)
				break
	return DataFrame(out_rows, columns=df.columns)

def excludeTags(df: DataFrame, tags: []) -> DataFrame:
	out_rows = []
	for i, row in df.iterrows():
		item_tags = [str(t).lower() for t in str(row['Tags']).strip().split(';')]
		good = True
		for t in [str(t).lower() for t in tags]:
			if t in item_tags:
				good = False
				break
		if good == True:
			out_rows.append(row)
	return DataFrame(out_rows, columns=df.columns)

def requireTags(df: DataFrame, tags: []) -> DataFrame:
	out_rows = []
	for i, row in df.iterrows():
		item_tags = [str(t).lower() for t in str(row['Tags']).strip().split(';')]
		good = True
		for t in [str(t).lower() for t in tags]:
			if t not in item_tags:
				good = False
				break
		if good == True:
			out_rows.append(row)
	return DataFrame(out_rows, columns=df.columns)

def format_entry(n):
	if n is None:
		return '--'
	elif type(n) == str:
		return n
	elif type(n) != float:
		return str(n)
	elif numpy.isnan(n):
		return '--'
	elif int(n) == n:
		return '%.0f' % n
	else:
		return '%.2f' % n

if __name__ == '__main__':
	main()