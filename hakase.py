#!/usr/bin/env python
"""
Hakase

Python type serialization library intended for lightweight storage and
communication with other processes.

TODO: Introduce line conformity - this project is missing it because it's
pretty old, and was written before I made a decision on whether or not
restricting the length of a line was a good idea.
"""
import struct, xxhash, brotli

__author__ = 'Naphtha Nepanthez'
__version__ = '0.0.1'
__license__ = 'MIT' # SEE LICENSE FILE
__all__ = ['Hakase', 'StaticHakase', 'dumps', 'loads']

class _HakaseShared(object):
	_TYPES = {
		'object'  : 0b0000,
		'array'   : 0b0001, # 1001 # immutable
		'blob'    : 0b0010, # 1010 # utf8
		'number'  : 0b0011, # 1011 # intentional integer
		'boolean' : 0b0100, # 1100 # null
		#           0b1001 IMMUTABLE ARRAY
		#           0b1010 UTF-8 STRING
		#           0b1011 INTEGER
		#           0b1100 NULL
	}
	
	_HEADER = bytearray(b'HK')
	
	_STRUCTS = {
		'size':    ['<B', 1], # unsigned char
		'type':    ['<B', 1], # unsigned char
		'boolean': ['<?', 1], # _Bool
		'hash':    ['<B', 1], # unsigned char
		'float':   ['<f', 4]  # float
	}
	
	_unpacker = (lambda *args, **kwargs: struct.unpack(*args[1:], **kwargs)[0])
	
	def int_byte_length(self, i: int, *, signed: bool = True) -> int:
		return ((i + ((i * signed) < 0)).bit_length() + 7 + signed) // 8
	
	def int_to_bytes(self, i: int, *, size: int = -1, signed: bool = True) -> bytes:
		length = self.int_byte_length(i, signed = signed)
		return i.to_bytes((lambda x, y: length if size < 1 else size)(length, size), byteorder='little', signed=signed)

	def int_from_bytes(self, b: bytes, *, signed: bool = True) -> int:
		return int.from_bytes(b, byteorder='little', signed=signed)
	
	def max_bl_in_array(self, encoded_list: list):
		return max(map((lambda x: self.int_byte_length(len(x), signed = False)), encoded_list))
	
	def _return_none(*args, **kwargs):
		return None
	
	def _blob_decode(self, blob):
		return blob.decode('utf8')

class _HakaseEncode(_HakaseShared):
	class InvalidEncodingType(Exception):
		pass
	
	def encode(self, i):
		if   type(i) in [int, float]:
			try:
				return self.type_number(i)
			except struct.error:
				raise OverflowError('Integer too large!')
		elif type(i) in [bool, type(None)]:
			return self.type_boolean(i)
		elif type(i) in [str, bytes, bytearray]:
			return self.type_blob(i)
		elif type(i) in [tuple, list]:
			return self.type_array(i)
		elif type(i) in [dict]:
			return self.type_object(i)
		else:
			raise self.InvalidEncodingType('Type {0} cannot be encoded.'.format(str(type(i))))
			
	def type_array(self, i):
		encoded = []
		for y in i:
			encoded.append(self.encode(y))
		
		maxsize = self.max_bl_in_array(encoded)
		
		output = bytearray().join([
			struct.pack(
				self._STRUCTS['type'][0],
				self._TYPES['array'] | (lambda x: 0b1000 if x == tuple else 0b0000)(type(i))
			),
			struct.pack(
				self._STRUCTS['size'][0],
				maxsize
			)
		])
			
		for z in encoded:
			output += bytearray().join([
				self.int_to_bytes(len(z), size = maxsize, signed = False),
				z
			])
			
		return output
		
	def type_object(self, i):
		encoded = []
		for k, v in i.items():
			encoded.append(self.encode(k))
			encoded.append(self.encode(v))
		
		maxsize = self.max_bl_in_array(encoded)
		
		output = bytearray().join([
			struct.pack(
				self._STRUCTS['type'][0],
				self._TYPES['object']
			),
			struct.pack(
				self._STRUCTS['size'][0],
				maxsize
			)
		])
			
		for z in encoded:
			output += bytearray().join([
				self.int_to_bytes(len(z), size = maxsize, signed = False),
				z
			])
			
		return output
		
	def type_number(self, i):
		if type(i) == int:
			out = self.int_to_bytes(i)
		else:
			out = struct.pack(self._STRUCTS['float'][0], i)
		
		return bytearray().join([
			struct.pack(
				self._STRUCTS['type'][0],
				self._TYPES['number'] | (lambda x: 0b1000 if x == int else 0b0000)(type(i))
			),
			out
		])

	def type_boolean(self, i):
		return bytearray().join([
			struct.pack(
				self._STRUCTS['type'][0],
				self._TYPES['boolean'] | (lambda x: 0b1000 if x == type(None) else 0b0000)(type(i))
			),
			struct.pack(
				self._STRUCTS['boolean'][0],
				(lambda x: False if type(x) == type(None) else x)(i)
			)
		])

	def type_blob(self, i):
		return bytearray().join([
			struct.pack(
				self._STRUCTS['type'][0],
				self._TYPES['blob'] | (lambda x: 0b1000 if x == str else 0b0000)(type(i))
			),
			(lambda x: bytearray(x.encode('utf8')) if type(x) == str else bytearray(x))(i)
		])
		
class _HakaseDecode(_HakaseShared):
	def decode(self, i):
		element_rough_type = self._unpacker(self._STRUCTS['type'][0], i[:self._STRUCTS['type'][1]]) & 0b0111
			
		return {
			self._TYPES['number']: self.type_number,
			self._TYPES['boolean']: self.type_boolean,
			self._TYPES['blob']: self.type_blob,
			self._TYPES['array']: self.type_array,
			self._TYPES['object']: self.type_object
		}[element_rough_type](i)

	def type_number(self, i):
		if bool(self._unpacker(self._STRUCTS['type'][0], i[:self._STRUCTS['type'][1]]) & 0b1000):
			return self.int_from_bytes(i[self._STRUCTS['type'][1]:])
		else:
			return self._unpacker(self._STRUCTS['float'][0], i[self._STRUCTS['type'][1]:])
		
	def type_boolean(self, i):
		return (lambda x: x(
				self._unpacker(self._STRUCTS['boolean'][0], i[self._STRUCTS['type'][1]:])
			)
		)(
			(lambda t: self._return_none if bool(t & 0b1000) else bool)(self._unpacker(self._STRUCTS['type'][0], i[:self._STRUCTS['type'][1]]))
		)
		
	def type_blob(self, i):
		return (lambda x: x(
				i[self._STRUCTS['type'][1]:]
			)
		)(
			(lambda t: self._blob_decode if bool(t & 0b1000) else bytearray)(self._unpacker(self._STRUCTS['type'][0], i[:self._STRUCTS['type'][1]]))
		)

	def type_array(self, i):
		index = 0
		conversion = (lambda t: tuple if t else list)(bool(self._unpacker(self._STRUCTS['type'][0], i[index:index+self._STRUCTS['type'][1]]) & 0b1000))
		index += self._STRUCTS['type'][1]
		element_size = self._unpacker(self._STRUCTS['size'][0], i[index:index+self._STRUCTS['size'][1]])
		index += self._STRUCTS['size'][1]

		output = []
		while index < len(i):
			length = self.int_from_bytes(i[index : index + element_size], signed = False)
			index += element_size
			output.append(self.decode(i[index : index + length]))
			index += length
			
		return conversion(output)
		
	def type_object(self, i):
		index = 1
		element_size = self._unpacker(self._STRUCTS['size'][0], i[index:index+self._STRUCTS['size'][1]])
		index += self._STRUCTS['size'][1]

		output = {}
		while index < len(i):
			length = self.int_from_bytes(i[index : index + element_size], signed = False)
			index += element_size
			key = self.decode(i[index : index + length])
			index += length
			
			length = self.int_from_bytes(i[index : index + element_size], signed = False)
			index += element_size
			value = self.decode(i[index : index + length])
			index += length
			
			output[key] = value
			
		return output
		
class Hakase(_HakaseShared):
	class CorruptFrameException(Exception):
		pass
		
	class InvalidEncodingType(Exception):
		pass
	
	def __init__(self):
		self.encoder = _HakaseEncode()
		self.decoder = _HakaseDecode()
		
	def dumps(self, i, compressed: bool = False, level: int = 11):
		"""
		This is the function for creating Hakase data.
		
		Parameters
		----------
		i :
			The primitive data to encode
		compressed : bool, optional
			Whether or not to compress the output with brotli.
			(Defaults to False)
		level : int, optional
			What compression level to use (Defaults to 11) (Ranges
			between (0 and 11)
		
		Returns
		-------
		data : bytearray
			The encoded version of the input data.
		
		Raises
		------
		Hakase.InvalidEncodingType
			Raised when a data type has been supplied to the encoder
			that cannot be encoded.
		OverflowError
			Raised when you attempt to encode an integer that is too big
		"""
		
		try:
			encoded = self.encoder.encode(i)
		except _HakaseEncode.InvalidEncodingType as e:
			raise self.InvalidEncodingType(e.message)
			
		checksum = struct.pack(self._STRUCTS['hash'][0], xxhash.xxh32(encoded).intdigest() & 0xFF)

		return bytearray().join([
			self._HEADER,
			struct.pack(self._STRUCTS['boolean'][0], compressed),
			(lambda x, y: brotli.compress(bytes(x), quality = level) if y else x)(bytearray().join([checksum, encoded]), compressed)
		])
		
	def loads(self, i):
		"""
		This is the function for decoding Hakase data back into Python
		data structures.
		
		Parameters
		----------
		i :
			The Hakase data to decode
		
		Returns
		-------
		data :
			The encoded version of the input data.
		
		Raises
		------
		Hakase.CorruptFrameException
			Raised when the input data is invalid in some way.
		"""
		
		index = 0
		if i[index:index+len(self._HEADER)] != self._HEADER:
			raise self.CorruptFrameException('Invalid input data header!')
		
		index += len(self._HEADER)

		compressed = self._unpacker(self._STRUCTS['boolean'][0], i[index:index+self._STRUCTS['boolean'][1]])
		if compressed:
			try:
				i = brotli.decompress(bytes(i[index+self._STRUCTS['boolean'][1]:]))
				
				index = 0
			except zstandard.ZstdError:
				raise self.CorruptFrameException('Unable to decompress data!')
		else:
			index += 1
		
		if self._unpacker(self._STRUCTS['hash'][0], i[index:index + self._STRUCTS['hash'][1]]) != (xxhash.xxh32(i[index + self._STRUCTS['hash'][1]:]).intdigest() & 0xFF):
			raise self.CorruptFrameException('The input data checksum did not match the rest of the data stream!')
		
		index += self._STRUCTS['hash'][1]
		
		return self.decoder.decode(i[index:])
		
class StaticHakase(object):
	@staticmethod	
	def dumps(*args, **kwargs):
		"""
		staticmethod alias of hakase.Hakase.dumps()
		"""
		return Hakase().dumps(*args, **kwargs)
				
	@staticmethod
	def loads(*args, **kwargs):
		"""
		staticmethod alias of hakase.Hakase.loads()
		"""
		return Hakase().loads(*args, **kwargs)
			
# Similar interface to the `json` library.
dumps = StaticHakase.dumps
loads = StaticHakase.loads

# Backwards compatibility with Hakase's predecessor, Khaki
StaticKhaki = StaticHakase
Khaki = Hakase
			
if __name__ == '__main__':
	test_data = {
		'stuff': [1, 2, 3, 'hello', {
			'world': True,
			'things': None
		}],
		'negative': -25,
		'numbers': [1, 2, 4, 8, 16, 32, 64, 128],
		'floats': [0.274, 0.56818, 29591.5, 2942.444, 992.32],
		'wowza': 'bazoingo',
		'big_number': 714980917575155763,
		'bytestest': b'\x00' * 2
	}
	
	dumped = dumps(test_data, compressed = False)
	loaded = loads(dumped)
	
	import sys, dill
	
	#sys.stdout.buffer.write(dill.dumps(test_data))
	sys.stdout.buffer.write(dumped)
	sys.stdout.flush()
	
	#print(len(brotli.compress(dill.dumps(test_data), quality = 11)))
	#print(len(dill.dumps(test_data)))
	#print(len(dumped))
	
	#print(dumped)
	#print(loaded)
