#!/usr/bin/python
 
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.node import Controller 
from mininet.cli import CLI
from functools import partial
from mininet.node import RemoteController
import os

import sys  # starting arguments

# Topology: switches interconnected in diamond topology (3 parallel paths, no cross-links); 3 hosts on each side of the diamond

class MyTopo(Topo):
    "Single switch connected to n hosts."
    def __init__(self, delay1 = 100, delay2 = 80, delay3 = 50, buffor_size = 1000, bandwidth = 1):
        Topo.__init__(self)
        s1=self.addSwitch('s1')
        s2=self.addSwitch('s2')
        s3=self.addSwitch('s3')
        s4=self.addSwitch('s4')
        s5=self.addSwitch('s5')
        h1=self.addHost('h1')
        h2=self.addHost('h2')
        h3=self.addHost('h3')
        h4=self.addHost('h4')
        h5=self.addHost('h5')
        h6=self.addHost('h6')

        self.addLink(h1, s1, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(h2, s1, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(h3, s1, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s1, s2, bw=int(bandwidth), delay= str(delay1) + 'ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s1, s3, bw=int(bandwidth), delay= str(delay2) + 'ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s1, s4, bw=int(bandwidth), delay= str(delay3) + 'ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s2, s5, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s3, s5, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s4, s5, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s5, h4, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s5, h5, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)
        self.addLink(s5, h6, bw=int(bandwidth), delay='0ms', loss=0, max_queue_size=int(buffor_size), use_htb=True)

def perfTest():
    "Create network and run simple performance test"
    if len(sys.argv) > 1:       # Running topology with self defined parameters
        topo = MyTopo(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:                       # Running default topology
        topo = MyTopo()
    #net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller=POXcontroller1)
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller=partial(RemoteController, ip='192.168.0.105', port=6633))
    net.start()
    print "Dumping host connections"
    dumpNodeConnections(net.hosts)
    h1,h2,h3=net.get('h1','h2','h3')
    h4,h5,h6=net.get('h4','h5','h6')
    s1,s2,s3,s4,s5=net.get('s1', 's2', 's3', 's4', 's5')
    h1.setMAC("0:0:0:0:0:1")
    h2.setMAC("0:0:0:0:0:2")
    h3.setMAC("0:0:0:0:0:3")
    h4.setMAC("0:0:0:0:0:4")
    h5.setMAC("0:0:0:0:0:5")
    h6.setMAC("0:0:0:0:0:6")
    s1.setMAC("1:0:0:0:0:1")
    s2.setMAC("1:0:0:0:0:2")
    s3.setMAC("1:0:0:0:0:3")
    s4.setMAC("1:0:0:0:0:4")
    s5.setMAC("1:0:0:0:0:5")
    CLI(net) # launch simple Mininet CLI terminal window
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    perfTest()

