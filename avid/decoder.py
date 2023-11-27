#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2023 Eileen Yoon <eyn@gmx.com>

from collections import namedtuple
from .utils import round_up

class AVDRange(namedtuple('AVDRange', ['iova', 'size', 'name'])):
	def __repr__(self):
		return f"[iova: {hex(self.iova).rjust(7+2)} size: {hex(self.size).rjust(7+2)} name: {str(self.name).ljust(11)}]"

class AVDDecoder:
	def __init__(self, parsercls, halcls, fpcls):
		self.parser = parsercls()
		self.hal = halcls()
		self.fpcls = fpcls
		self.ctx = None
		self.stfu = False
		self.ffp = {}
		self.last_iova = 0x0
		self.used = []

	def log(self, x):
		if (not self.stfu):
			print(f"[AVD] {x}")

	def reset_allocator(self):
		self.last_iova = 0x0
		self.used = []

	def allocate(self, size, pad=0x0, padb4=0x0, align=0x0, name=""):
		iova = self.last_iova
		if (align):
			iova = round_up(iova, align)
		if (padb4):
			iova += padb4
		if (not name):
			name = "range_%d" % len(self.used)
		self.used.append(AVDRange(iova, size, name))
		self.last_iova = iova + size + pad
		return iova

	def allocator_move_up(self, start):
		assert(start >= self.last_iova)
		self.last_iova = start

	def dump_ranges(self):
		for i,x in enumerate(self.used):
			s = f"[{str(i).rjust(2)}] {x}"
			if ("rvra" in x.name):
				s += f" {hex(x.iova >> 7).rjust(5+2)}"
			self.log(s)
		self.log("last iova: 0x%08x" % (self.last_iova))

	def init_slice(self):
		pass

	def finish_slice(self):
		pass

	def refresh(self, sl): # sl is RO
		pass

	def setup(self, path):
		raise NotImplementedError()

	def decode(self, sl):
		self.ctx.active_sl = sl
		self.init_slice()
		inst_stream = self.hal.decode(self.ctx, sl)
		self.ffp = self.make_ffp(inst_stream)
		self.finish_slice()
		return inst_stream

	def make_ffp(self, inst_stream):
		ffp = self.fpcls._ffpcls.new()
		for inst in inst_stream:
			if (isinstance(inst.idx, int)):
				ffp[inst.name][inst.idx] = inst.val
			else:
				ffp[inst.name] = inst.val
		return ffp
