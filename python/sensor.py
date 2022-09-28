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
    def __init__(self, sensor_id, address, sensing_factor, noise_samples, noise_split, noise_iterations):
        gr.sync_block.__init__(self,
            name="sensor",
            in_sig=[np.complex64],
            out_sig=[np.complex64])

        self.sensor_id = sensor_id
        self.address = address
        self.threshold = pow(10.0, -111 / 10.0)
        
        self.ignore_samples = None
        self.samples = None
        self.index = 0
        self.sensing_factor = sensing_factor

        self.stage = 0  # [0 - noise estimation; 1 - sensing]

        self.noise_samples_count = noise_samples
        self.noise_samples = np.zeros((noise_samples, ), dtype=np.complex64)
        self.noise_index = 0
        self.noise_itr = 0

        self.noise_data = np.zeros((noise_split, noise_iterations))
        self.noise_split = noise_split
        self.noise_iterations = noise_iterations

        

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        out[:] = in0

        # LK
        if self.stage == 0:
            # Noise estimation and register

            for i in range(len(in0)):
                self.noise_samples[self.noise_index] = in0[i]
                self.noise_index += 1
                if self.noise_index == self.noise_samples_count:
                    print('Noise estimation... ' + str(self.noise_itr + 1) + '/' + str(self.noise_iterations))
                    self.noise_index = 0

                    data = np.fft.fft(self.noise_samples)
                    data = np.fft.fftshift(data)

                    power0 = pow(abs(data), 2.0) / self.noise_samples_count
                    power0 = power0 / 1e3
                    subband = int(np.floor(self.noise_samples_count / self.noise_split))
                    for sub in range(self.noise_split):
                        p = power0[sub * subband: (sub + 1) * subband]
                        self.noise_data[sub, self.noise_itr] = 10.0*np.log10(np.nanmean(p))

                    self.noise_itr += 1
                    if self.noise_itr == self.noise_iterations:
                        self.stage = 1
                        
                        print('Noise estimation result: ')
                        print(' index; mean; std')
                        keep = np.argsort(np.std(self.noise_data, axis=1))
                        keep = keep[0:len(keep)/2]

                        mean_v = np.mean(self.noise_data, axis=1)
                        mean_v = mean_v[keep]
                        selected = np.argsort(mean_v)
                        selected = keep[selected[0]]
                        
                        for j in range(self.noise_split): 

                            print("%2d: %3.2f dBm; %.2f dB; %s %s" % (j,
                             np.mean(self.noise_data[j, :]), np.std(self.noise_data[j, :]),
                             '' if j in keep else 'ignore', 'SELECTED' if j == selected else ''))

                        self.threshold = np.mean(self.noise_data[selected, :]) #+ 10.0*np.log10(self.noise_split)
                        query = {'id': self.sensor_id, 'noise_level': self.threshold}
                        response = requests.get(self.address + '/register', params=query)
                        self.server_time = float(response.json()['timestamp'])
                        self.n_samples = int(response.json()['n_samples'])
                        print('Server: calculated threshold ' + str(float(response.json()['threshold'])) + ' dBm')
                        print('Server: number of samples ' + str(int(response.json()['n_samples'])))
                        self.threshold = pow(10.0, float(response.json()['threshold']) / 10.0)
                        self.local_start_time = time.time()

                        self.ignore_samples = int((1.0 - self.sensing_factor) * self.n_samples / self.sensing_factor)
        
                        self.samples = np.zeros((self.n_samples, ), dtype=np.complex64)
           
        else:
            # Sensing
            for i in range(len(in0)):
                if self.index >= 0: 
                    self.samples[self.index] = in0[i]
                
                self.index += 1

                if self.index == self.n_samples:
                    self.index = -self.ignore_samples
                    
                    data = pow(abs(self.samples), 2.0) / 1e3
                    data[data == 0] = np.nan
                    mean = np.nanmean(data)
                    #mean = 10.0 * np.log10(mean)
                    #print(f"{mean} [{10.0*np.log10(self.threshold)}]")
                    diff = 10.0 * np.log10(mean) - 10.0*np.log10(self.threshold)
                    text = '(%.2f)' % diff
                    decision = mean >= self.threshold
                    if decision:
                        print('Sensing... ' + text + ' SIGNAL DETECTED') 
                    else:
                        print('Sensing... ' + text )

                    timestamp = self.server_time + (time.time() - self.local_start_time)
                    
                    query = {'id': self.sensor_id, 'timestamp': timestamp, 'detected': decision}
                    requests.get(self.address + '/report', params=query)


 
        return len(output_items[0])

