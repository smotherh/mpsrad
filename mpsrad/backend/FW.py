#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 16 11:24:10 2017

@author: larsson
"""
import socket
import struct
import numpy as np
from time import sleep
from . import dummy_backend

class FW:
	""" Connection to fast fourier transform spectrometer
	Functions:
		init:
			Connects to the machine and initialized how it will be run
		close:
			Remove the connect to the machine and initiate simple clearing
		run:
			Runs the machine and fills requested channel
		save_data:
			Saves data to file
	"""
	def __init__(self,
			library=None,
			name='AFFTS',
			host='localhost',
			tcp_port=25144,
			udp_port=16210,
			channels=np.array([8192,8192]),
			integration_time=1000,
			blank_time=1,
			data_storage_containers=4):
		assert isinstance(integration_time,int),"Integration in integers"
		assert integration_time < 5001,"5000 ms integration time is maximum"

		self.name=name

		self._bytes=np.sum(channels)*4
		self._boards=len(channels)
		self._channels=channels
		self._tcp_port=tcp_port
		self._udp_port=udp_port
		self._host=host
		self._integration_time=str(int(integration_time * 1000))
		self._blank_time=str(int(blank_time * 1000))
		self._copies_of_vectors=int(data_storage_containers)

		self._initialized=False
		self._sent=False

	def init(self):
		assert not self._initialized,"Cannot init initialized FFTS"

		try:

			self._tcp_sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			self._ip=socket.gethostbyname(self._host)
			self._tcp_sock.connect((self._ip,self._tcp_port))

			self._udp_sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
			self._udp_addr=(self._ip,self._udp_port)
			self._udp_sock.sendto(b'AFFTS:cmdMode INTERNAL ',self._udp_addr)
			sleep(0.1)

			self._set_integration_time(self._integration_time)
			sleep(0.1)
			self._set_blank_time(self._blank_time)
			sleep(0.1)
			s=''
			for i in range(len(self._channels)):
				s += '1 '
				self._udp_sock.sendto(('AFFTS:Band'+str(i+1)+':cmdNumspecchan '
					+ str(self._channels[i]) +
					' ').encode("ascii"),self._udp_addr)
				sleep(0.1)
			self._udp_sock.sendto(('AFFTS:cmdUsedsections '+s).encode("ascii"),
				self._udp_addr)
			sleep(0.1)
			self._udp_sock.sendto(b'AFFTS:configure ',self._udp_addr)
			sleep(0.3)
			self._udp_sock.sendto(b'AFFTS:calADC ',self._udp_addr)
			self._initialized=True
			self._sent=False
			self._data=[]
#			for i in range(self._copies_of_vectors):
#				self._data.append(np.array([]))
			for i in range(self._copies_of_vectors):
				self._data.append(np.zeros((self._channels[0]), dtype=np.float64))
			sleep(3.0)
		except :
			dummy_FW=dummy_backend.dummy_spectrometer()

	def _set_integration_time(self,time):
		t=str(time)+' '
		self._udp_sock.sendto(('AFFTS:cmdSynctime '+t).encode("ascii"),
			self._udp_addr)

	def _set_blank_time(self,time):
		t=str(time)+' '
		self._udp_sock.sendto(('AFFTS:cmdBlanktime '+t).encode("ascii"),
			self._udp_addr)

	def run(self):
		assert self._initialized,"Cannot run uninitialized FFTS"
		assert not self._sent,"Cannot resend data,download first"

		self._udp_sock.sendto(b'AFFTS:dump 1 ',self._udp_addr)
		self._sent=True

	def get_data(self,i=0):
		assert self._initialized,"Cannot run uninitialized FFTS"
		assert i < self._copies_of_vectors and i > -1,"Bad index"
		assert self._sent,"Cannot download data before running machine"

		header=self._tcp_sock.recv(64,socket.MSG_WAITALL)
		h=struct.unpack('4s4sI8s28s4I',header)
		print(h)
		if h[2] > 64:
			d=self._tcp_sock.recv(h[2]-64,socket.MSG_WAITALL)
			d=struct.unpack(str((h[2]-64)//4)+'f',d)
			self._data[i]=np.array(d,dtype=np.float32)
			self._time=h[4].decode('utf8').strip()
		self._sent=False

	def save_data(self,basename="/home/waspam/data/test/FW",binary=True):
		"""Saves data to file at basename+filename
		Uses last access-time to server socket as filename
		Saves with numpy binary format if binary is true or as ascii otherwise
		"""
		assert self._initialized,"No data exists for an uninitialized FFTS"
		assert len(self._time),"Must call run() succesfully to save data"

		filename=self._time

		if binary: np.save(basename+filename,self._data)
		else: np.savetxt(basename+filename,self._data)

		self._time=''

	def close(self):
		"""Disconnect from both servers of the AFFTS and sends stop to AFFTS
		"""
		assert self._initialized,"Cannot close uninitialized FFTS"

		self._tcp_sock.close()
		self._udp_sock.sendto(b'AFFTS:stop ',self._udp_addr)
		self._udp_sock.close()
		self._initialized=False