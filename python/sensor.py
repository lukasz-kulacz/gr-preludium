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

import requests
import numpy as np
from gnuradio import gr

class sensor(gr.sync_block):
    """
    docstring for block sensor
    """
    def __init__(self, sensor_id, address, threshold, n_samples, sensing_factor):
        gr.sync_block.__init__(self,
            name="sensor",
            in_sig=[np.complex64],
            out_sig=[np.complex64])

        self.sensor_id = sensor_id
        self.address = address
        self.threshold = pow(10.0, threshold / 10.0)
        self.n_samples = n_samples
        self.ignore_samples = int((1.0 - sensing_factor) * n_samples / sensing_factor)
        
        self.samples = np.zeros((n_samples, ), dtype=np.complex64)
        self.index = -1

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        
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
                
                query = {'id': self.sensor_id, 'detected': decision}
                requests.get(self.address, params=query)


        out[:] = in0
        return len(output_items[0])

