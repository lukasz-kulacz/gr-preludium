#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2022 <+YOU OR YOUR COMPANY+>.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import time
import requests
import numpy as np
from gnuradio import gr

class sensor(gr.sync_block):
    """
    docstring for block sensor
    """
    def __init__(self, sensor_id, address):
        gr.sync_block.__init__(self,
            name="sensor",
            in_sig=[np.complex64],
            out_sig=[np.complex64])

        # from GUI
        self.sensor_id = sensor_id
        self.address = address

        # params
        self.request_every_sec = 3.0
        self.freq = 1e6
        self.samp_rate = 1e6
        self.lo_offset = 0.0

        # set
        self.stage = 0  # [0 - get config; 1 - noise estimation; 2 - sensing]
        self.last_request_time = time.time() - self.request_every_sec 


    def get_freq(self):
        return self.freq

    def get_samp_rate(self):
        return self.samp_rate

    def get_lo_offset(self):
        return self.lo_offset

    def process_noise(self):
        data = np.fft.fft(self.noise_samples)
        data = np.fft.fftshift(data)

        power0 = pow(abs(data), 2.0) / self.noise_samples_count
        power0 = power0 / 1e3
        subband = int(np.floor(self.noise_samples_count / self.all_blocks_count))
        for sub in range(self.all_blocks_count):
            p = power0[sub * subband: (sub + 1) * subband]
            self.noise_data[sub, self.noise_itr] = 10.0*np.log10(np.nanmean(p))


    def register(self):
        
        self.mask = np.zeros((self.all_blocks_count, ), dtype=bool)
        self.mask[self.ignore_side_blocks:-self.ignore_side_blocks] = True
        self.threshold = np.mean(self.noise_data, axis=1)
        
        query = {'id': self.sensor_id, 'noise': self.threshold[self.mask].tolist()}
        try:
            response = requests.post(self.address + '/register', json=query)
            assert response.json()['success'], 'Not successful registration: ' + response.json()
            assert len(response.json()['threshold']) == self.block_count, 'Wrong length of request and response'
            
            print('Noise estimation result: ')
            print(' index; std; mean; threshold')
            for j in range(self.all_blocks_count): 
                txt_ignore = '' if self.ignore_side_blocks <= j < self.all_blocks_count - self.ignore_side_blocks else 'ignore'
                txt_th = response.json()['threshold'][j - self.ignore_side_blocks] if self.ignore_side_blocks <= j < self.all_blocks_count - self.ignore_side_blocks else np.nan
                print("%2d: %.2f dB; %3.2f dBm; %3.2f dBm; %s" % (j, np.std(self.noise_data[j, :]),
                    np.mean(self.noise_data[j, :]), txt_th, txt_ignore))
            self.threshold[self.mask] = response.json()['threshold']
            self.threshold[self.mask] += 1.0

            self.local_start_time = time.time()

            self.stage += 1
            self.index = 0

        except Exception as ex:
            print('Problem with registration. Registration query: ')
            print(query)
            print('Error: ')
            print(ex)
            self.stage = 0

    def process_sensing(self):
        result = np.zeros((self.all_blocks_count, ))
        detection = np.zeros((self.all_blocks_count, ), dtype=bool)
        data = np.fft.fft(self.samples)
        data = np.fft.fftshift(data)


        power0 = pow(abs(data), 2.0) / self.n_samples
        power0 = power0 / 1e3
        subband = int(np.floor(self.n_samples / self.all_blocks_count))
        txt = "["
        for sub in range(self.all_blocks_count):
            if self.mask[sub]:
                p = power0[sub * subband: (sub + 1) * subband]
                result[sub] = 10.0*np.log10(np.nanmean(p))
                #txt += '%3.2f' % (result[sub])
                
                if result[sub] >= self.threshold[sub]:
                    detection[sub] = True
                    txt += "1"
                else:
                    pass
                    txt += "0"
            else:
                pass
        txt += "]"
        print(txt)

        try:
            timestamp = self.server_time + (time.time() - self.local_start_time)
                    
            query = {'id': self.sensor_id, 'timestamp': timestamp, 'detection': detection[self.mask].tolist()}
            result = requests.post(self.address + '/report', json=query)
            assert result.status_code == 200, 'Status code: ' + str(result.status_code)
            assert result.json()['success'], 'Not successful report ' + result.json()
        except Exception as ex:
            print('Problem with report to server')
            print(ex)
            self.stage = 0

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        out[:] = in0

        if self.stage == 0:
            if time.time() - self.last_request_time > self.request_every_sec:
                try:
                    self.last_request_time = time.time()
                    response = requests.get(self.address + '/config', params={'id': self.sensor_id}).json()
                    print(' ')
                    print('--------------------------------------------------------')
                    print('Server get "/config" response:')
                    for key in response:
                        print(' >> %s: %s' % (key, response[key]))
                    print('--------------------------------------------------------')

                    self.server_time = float(response['current_time'])
                    self.block_count = int(response['blocks_count'])
                    self.samp_rate = float(response['samp_rate'])
                    self.all_blocks_count = int(response['all_blocks_count'])
                    self.noise_samples_count = int(response['noise_samples'])
                    self.noise_iterations = int(response['noise_steps'])
                    self.n_samples = int(response['common_n'])
                    self.lo_offset = float(response['lo_offset'])
                    self.freq = float(response['freq'])
                    self.sensing_time = float(response['sensing_time'])
                    self.ignore_side_blocks = int(response['ignore_side_blocks'])

                    self.stage += 1
                    self.noise_index = 0
                    self.noise_itr = 0

                    self.noise_samples = np.zeros((self.noise_samples_count, ), dtype=np.complex64)
                    self.noise_data = np.zeros((self.all_blocks_count, self.noise_iterations))
                    
                    self.ignore_samples = int((1.0 - self.sensing_time) * self.n_samples / self.sensing_time)
                    self.samples = np.zeros((self.n_samples, ), dtype=np.complex64)

                except Exception as ex:
                    print('Problem with server connection (or output parsing)...')
                    print(ex)

            
        elif self.stage == 1:
            for i in range(len(in0)):
                self.noise_samples[self.noise_index] = in0[i]
                self.noise_index += 1
                if self.noise_index == self.noise_samples_count:
                    print('Noise estimation... ' + str(self.noise_itr + 1) + '/' + str(self.noise_iterations))
                    self.noise_index = 0
                    self.process_noise()
                    self.noise_itr += 1
                    if self.noise_itr == self.noise_iterations:
                        self.register()
                        break

        elif self.stage == 2:
            for i in range(len(in0)):
                if self.index >= 0: 
                    self.samples[self.index] = in0[i]
                self.index += 1
                if self.index == self.n_samples:    
                    self.index = -self.ignore_samples
                    self.process_sensing()

        return len(output_items[0])
