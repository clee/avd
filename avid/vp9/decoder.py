#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2023 Eileen Yoon <eyn@gmx.com>

from ..decoder import AVDDecoder
from ..utils import *
from .halv3 import AVDVP9HalV3
from .parser import AVDVP9Parser
from .probs import AVDVP9Probs
from .types import *

class AVDVP9Ctx(dotdict):
	pass

class AVDVP9Decoder(AVDDecoder):
	def __init__(self):
		super().__init__(AVDVP9Parser, AVDVP9HalV3)

	def new_context(self):
		self.ctx = AVDVP9Ctx()
		ctx = self.ctx

		ctx.access_idx = 0
		ctx.width = -1
		ctx.height = -1
		ctx.active_sl = None

		ctx.inst_fifo_count = 7
		ctx.inst_fifo_idx = 0

	def allocate(self):
		ctx = self.ctx
		# constants
		ctx.inst_fifo_iova = 0x2c000
		ctx.inst_fifo_size = 0x100000
		# [0x002c0, 0x01300, 0x02340, 0x03380, 0x043c0, 0x05400, 0x06440]
		# ctx.inst_fifo_iova + (n * (ctx.inst_fifo_size + 0x4000))

		ctx.probs_size = AVDVP9Probs.sizeof() # 0x774
		ctx.probs_count = 4  # rotating FIFO slots
		ctx.probs_base_addr = 0x4000  # (round_up(ctx.probs_size), 0x4000) * ctx.probs_count

		ctx.y_addr = 0x768100
		ctx.uv_addr = 0x76c900
		ctx.slice_data_addr = 0x774000

		ctx.pps_tile_addrs = [0] * 4

		if   (ctx.width == 128 and ctx.height == 64):
			ctx.sps_tile_base_addr = 0x8cc000 >> 8  # [0x8cc0, 0x8d40, 0x8e40, 0x8ec0, 0x8f40, 0x8fc0]
			ctx.pps_tile_base_addr = 0x87c000 >> 8  # [0x8dc0, 0x8940, 0x87c0, 0x8840]
			ctx.pps_tile_addrs[3] = ctx.pps_tile_base_addr + 0x80
			ctx.pps_tile_addrs[1] = ctx.pps_tile_base_addr + 0x80 + 0x100  # 0x180
			ctx.pps_tile_addrs[0] = ctx.pps_tile_base_addr + 0x80 + 0x100 + 0x480  # 0x600

			ctx.rvra0_addrs = [0x0ef80, 0x0eb82, 0x0f080, 0x0ec12]
			ctx.rvra1_addrs = [0x0f180, 0x12082, 0x0f280, 0x12112]
			ctx.rvra2_addrs = [0x0f380, 0x12382, 0x0f480, 0x12412]
			ctx.rvra3_addrs = [0x0f580, 0x12682, 0x0f680, 0x12712]
			ctx.rvra4_addrs = [0x0f380, 0x12202, 0x0f480, 0x12292]
			ctx.rvra5_addrs = [0x0f580, 0x12382, 0x0f680, 0x12412]
			ctx.rvra6_addrs = [0x0f380, 0x12682, 0x0f480, 0x12712]

		elif (ctx.width == 1024 and ctx.height == 512):
			ctx.sps_tile_base_addr = 0x9d4000 >> 8  # [0x9d40, 0x9dc0, 0x9ec0, 0x9f40, 0x9fc0, 0xa040]
			ctx.pps_tile_base_addr = 0x964000 >> 8  # [0x9e40, 0x99c0, 0x9640, 0x97c0]
			ctx.pps_tile_addrs[3] = ctx.pps_tile_base_addr + 0x180
			ctx.pps_tile_addrs[1] = ctx.pps_tile_base_addr + 0x180 + 0x200  # 0x380
			ctx.pps_tile_addrs[0] = ctx.pps_tile_base_addr + 0x180 + 0x200 + 0x480  # 0x800

			ctx.rvra0_addrs = [0x0ff80, 0x0eb80, 0x10a00, 0x10000]
			ctx.rvra1_addrs = [0x15780, 0x14380, 0x16200, 0x15800]
			ctx.rvra2_addrs = [0x19000, 0x17c00, 0x19a80, 0x19080]
			ctx.rvra3_addrs = [0x1c880, 0x1b480, 0x1d300, 0x1c900]
			ctx.rvra4_addrs = [0x19000, 0x17c00, 0x19a80, 0x19080]

		else:
			raise ValueError("not impl")

		ctx.pps_tile_addrs[2] = ctx.pps_tile_base_addr + 0x0

	def refresh(self, sl):
		ctx = self.ctx
		width = sl.frame_width
		height = sl.frame_height
		if (not ((width == ctx.width) and (height == ctx.height))):
			self.log("dimensions changed from %dx%d -> %dx%d" % (ctx.width, ctx.height, width, height))
			ctx.width = width
			ctx.height = height
			self.allocate()

		# update addresses driver needs to access
		probs_slot = ctx.access_idx % ctx.probs_count
		# plus a page for some reason
		ctx.probs_addr = ctx.probs_base_addr + (probs_slot * (round_up(ctx.probs_size, 0x4000) + 0x4000))

	def setup(self, path, num=0):
		self.new_context()
		slices = self.parser.parse(path, num)
		self.refresh(slices[0])
		return slices

	def init_slice(self):
		ctx = self.ctx; sl = self.ctx.active_sl
		self.refresh(sl)

	def finish_slice(self):
		ctx = self.ctx; sl = self.ctx.active_sl
		ctx.access_idx += 1
