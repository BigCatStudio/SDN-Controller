# The program implements a simple controller for a network with 6 hosts and 5 switches.
# The switches are connected in a diamond topology (without vertical links):
#    - 3 hosts are connected to the left (s1) and 3 to the right (s5) edge of the diamond.
# Overall operation of the controller:
#    - default routing is set in all switches on the reception of packet_in messages form the switch,
#    - then the routing for (h1-h4) pair in switch s1 is changed every one second in a round-robin manner to load balance the traffic through switches s3, s4, s2. 

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.packet_base import packet_base
from pox.lib.packet.packet_utils import *
import pox.lib.packet as pkt
from pox.lib.recoco import Timer
import time


log = core.getLogger()
 
s1_dpid=0
s2_dpid=0
s3_dpid=0
s4_dpid=0
s5_dpid=0
 
s1_p1=0
s1_p4=0
s1_p5=0
s1_p6=0
s2_p1=0
s3_p1=0
s4_p1=0
 
pre_s1_p1=0
pre_s1_p4=0
pre_s1_p5=0
pre_s1_p6=0
pre_s2_p1=0
pre_s3_p1=0
pre_s4_p1=0
 
turn=0

#******************************************************************************************************************************************
#******************************************************************************************************************************************
start_time = 0.0
sent_time1=0.0
sent_time2=0.0
received_time1 = 0.0
received_time2 = 0.0
src_dpid = 0
dst_dpid_s2 = 0
dst_dpid_s3 = 0
dst_dpid_s4 = 0
mytimer = 0
OWD1 = 0.0
OWD2 = 0.0

measured_delay_s2 = 0.0
measured_delay_s3 = 0.0
measured_delay_s4 = 0.0

measures_amount_s2 = 0
measures_amount_s3 = 0
measures_amount_s4 = 0

measures_mean_s2 = 0.0
measures_mean_s3 = 0.0
measures_mean_s4 = 0.0

SWITCH2_READY = 1   # S1 - S2
SWITCH2_WORKING = 2 # S1 - S2
SWITCH3_READY = 3   # S1 - S3
SWITCH3_WORKING = 4 # S1 - S3
SWITCH4_READY = 5   # S1 - S4
SWITCH4_WORKING = 6 # S1 - S4

current_switch = SWITCH2_READY    # Get hold of currently measured delay beewteen switches

routing_table = None



link_s1_s2 = None
link_s1_s3 = None
link_s1_s4 = None

class RoutingTable:
  def __init__(self, s1_dpid, s5_dpid):
    self.s1_dpid = s1_dpid
    self.s5_dpid = s5_dpid

    self.switch1 = {
      "10.0.0.1" : 1,
      "10.0.0.2" : 2,
      "10.0.0.3" : 3,
      "10.0.0.4" : 4,
      "10.0.0.5" : 5,
      "10.0.0.6" : 6
    }
    self.switch5 = {
      "10.0.0.1" : 1,
      "10.0.0.2" : 2,
      "10.0.0.3" : 3,
      "10.0.0.4" : 4,
      "10.0.0.5" : 5,
      "10.0.0.6" : 6
    }

  def change_routes(self, dpid, address, port):
    if(dpid == self.s1_dpid):
      self.switch1[address] = port
    elif(dpid == self.s5_dpid):
      self.switch5[address] = port

  def print_routes(self, dpid):
    if(dpid == self.s1_dpid):
      for route in self.switch1.items():
        print "Switch1 route: ", route
    elif(dpid == self.s5_dpid):
      for route in self.switch5.items():
        print "Switch5 route: ", route


class Intent:     # Class to store information about all intents
  bandwidth_latency = 200  # Maximal bandwidth latency for connection Mb/s
  bytes_amount = 20000000  # Maximal bytes amount per second, if larger set new traffic to other link with lower B/s 
  src_address = "10.0.0.1" # Source address for intent to check parameters
  dst_address = "10.0.0.6" # Destiantion address for intent to check parameters
  intent = 1

  @classmethod
  def change_intent(cls, intent):
    cls.intent = intent
    if(intent == 1):
      cls.bandwidth_latency = 200
      cls.bytes_amount = 20000000
      cls.src_address = "10.0.0.1"
      cls.dst_address = "10.0.0.6"
    elif(intent == 2):
      Intent.bandwidth_latency = 100
      Intent.bytes_amount = 10000000
      Intent.src_address = "10.0.0.2"
      Intent.dst_address = "10.0.0.5"


class Link:    # Class to store which port to choose for every dst address 
  def __init__(self, src_dpid, dst_dpid, src_port, bw_src_port):
    self.src_dpid = src_dpid
    self.dst_dpid = dst_dpid
    self.src_port = src_port
    self.bw_src_port = bw_src_port
    self.bytes_amount = 0
    self.previous_bytes_amount = 0
    self.bandwidth_latency = 0


class AvailableRoutes:
  Intent_src_address = "10.0.0.1"
  Intent_dst_address = "10.0.0.6"
  Intent_src_port = 5
  Intent_bw_port = 2

  Normal1_src_address = "10.0.0.1"
  Normal1_dst_address = "10.0.0.6"
  Normal1_src_port = 5
  Normal1_bw_port = 2

  Normal2_src_address = "10.0.0.1"
  Normal2_dst_address = "10.0.0.6"
  Normal2_src_port = 5
  Normal2_bw_port = 2

  @classmethod
  def set_available(cls):
    if Intent.intent == 1:
      cls.Normal1_src_address = "10.0.0.2"
      cls.Normal1_dst_address = "10.0.0.5"
      cls.Normal1_src_port = 6
      cls.Normal1_bw_port = 3

      cls.Normal2_src_address = "10.0.0.3"
      cls.Normal2_dst_address = "10.0.0.4"
      cls.Normal2_src_port = 4
      cls.Normal2_bw_port = 1
    elif Intent.intent == 2 or Intent.intent == 3:
      cls.Normal1_src_address = "10.0.0.1"
      cls.Normal1_dst_address = "10.0.0.6"
      cls.Normal1_src_port = 6
      cls.Normal1_bw_port = 3

      cls.Normal2_src_address = "10.0.0.3"
      cls.Normal2_dst_address = "10.0.0.4"
      cls.Normal2_src_port = 4
      cls.Normal2_bw_port = 1


#probe protocol packet definition; only timestamp field is present in the header (no payload part)
class myproto(packet_base):
  def __init__(self):
     packet_base.__init__(self)
     self.timestamp = 0

  def hdr(self, payload):
     return struct.pack('!I', self.timestamp) # code as unsigned int (I), network byte order (!, big-endian - the most significant byte of a word at the smallest memory address)

#******************************************************************************************************************************************
#******************************************************************************************************************************************

def getTheTime():  #function to create a timestamp
  flock = time.localtime()
  then = "[%s-%s-%s" %(str(flock.tm_year),str(flock.tm_mon),str(flock.tm_mday))
 
  if int(flock.tm_hour)<10:
    hrs = "0%s" % (str(flock.tm_hour))
  else:
    hrs = str(flock.tm_hour)
  if int(flock.tm_min)<10:
    mins = "0%s" % (str(flock.tm_min))
  else:
    mins = str(flock.tm_min)
 
  if int(flock.tm_sec)<10:
    secs = "0%s" % (str(flock.tm_sec))
  else:
    secs = str(flock.tm_sec)

  then +="]%s.%s.%s" % (hrs,mins,secs)
  return then

def switch_intent():
  if Intent.intent == 1:
    Intent.change_intent(1)
  # elif Intent.intent == 2:
  #   Intent.change_intent(1)

def send_probe_packet(src_dpid, src_MAC_addr, dst_dpid, dst_MAC_addr, dst_port):
  global start_time, sent_time1, sent_time2
  if src_dpid <>0 and not core.openflow.getConnection(src_dpid) is None:

    #send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(src_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time1=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch0

    #sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto()
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr(src_MAC_addr)
    e.dst = EthAddr(dst_MAC_addr)
    e.type=0x5577 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=dst_port)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - start_time) #set the timestamp in the probe packet
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(src_dpid).send(msg)
    #print "=====> probe sent: f=", f.timestamp, " after=", int(time.time()*1000*10 - start_time), " [10*ms]"

  if dst_dpid <>0 and not core.openflow.getConnection(dst_dpid) is None:
    #send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(dst_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    sent_time2=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch1

def measure_delays():
  global start_time, sent_time1, sent_time2, src_dpid, dst_dpid_s2, dst_dpid_s3, dst_dpid_s4, current_switch

  if(current_switch == SWITCH2_READY):
    send_probe_packet(src_dpid, "1:0:0:0:0:1", dst_dpid_s2, "1:0:0:0:0:2", 4)
    current_switch = SWITCH2_WORKING
  elif(current_switch == SWITCH3_READY):
    send_probe_packet(src_dpid, "1:0:0:0:0:1", dst_dpid_s3, "1:0:0:0:0:3", 5)
    current_switch = SWITCH3_WORKING
  elif(current_switch == SWITCH4_READY):
    send_probe_packet(src_dpid, "1:0:0:0:0:1", dst_dpid_s4, "1:0:0:0:0:4", 6)
    current_switch = SWITCH4_WORKING

def correct_measures_delay(delay):
  if delay > 100:
    delay = delay - 30
  elif delay > 50:
    delay = delay - 20
  else:
    delay = delay - 7
  return delay

def set_routing ():
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid, routing_table
  global measured_delay_s2, measured_delay_s3, measured_delay_s4
  global measures_amount_s2, measures_amount_s3, measures_amount_s4
  global measures_mean_s2, measures_mean_s3, measures_mean_s4
  global link_s1_s2, link_s1_s3, link_s1_s4

  core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))

  measures_mean_s2 = measured_delay_s2/measures_amount_s2
  measures_mean_s3 = measured_delay_s3/measures_amount_s3
  measures_mean_s4 = measured_delay_s4/measures_amount_s4

  print "Link S1-S2 mean delay: ", measures_mean_s2
  print "Link S1-S3 mean delay: ", measures_mean_s3
  print "Link S1-S4 mean delay: ", measures_mean_s4

  link_s1_s2.bandwidth_latency = correct_measures_delay(measures_mean_s2)
  link_s1_s3.bandwidth_latency = correct_measures_delay(measures_mean_s3)
  link_s1_s4.bandwidth_latency = correct_measures_delay(measures_mean_s4)

  print "Link S1-S2 corrected delay: ", link_s1_s2.bandwidth_latency
  print "Link S1-S3 corrected delay: ", link_s1_s3.bandwidth_latency
  print "Link S1-S4 corrected delay: ", link_s1_s4.bandwidth_latency

  # ***************** Setting route for Intent **************
  links_delays = [link_s1_s2, link_s1_s3, link_s1_s4]
  links_delays.sort(key=lambda x: x.bandwidth_latency)
  intent_set = False
  
  print "Intent Latency: ", Intent.bandwidth_latency
  print "Intent dst adr:", Intent.dst_address, " src port:", Intent.src_address

  if links_delays[0].bandwidth_latency < Intent.bandwidth_latency and links_delays[0].src_port != routing_table.switch1[Intent.dst_address]  and links_delays[0].bw_src_port != routing_table.switch5[Intent.src_address]:
    print "******** Intent Route Changed ********"
    routing_table.change_routes(s1_dpid, Intent.dst_address, links_delays[0].src_port)
    routing_table.change_routes(s5_dpid, Intent.src_address, links_delays[0].bw_src_port)
    print "Switch_1 DST address: ", Intent.dst_address, "  DST port: ", links_delays[0].src_port
    print "Switch_5 DST address: ", Intent.src_address, "  DST port: ", links_delays[0].bw_src_port

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = Intent.dst_address
    msg.actions.append(of.ofp_action_output(port = links_delays[0].src_port))
    core.openflow.getConnection(s1_dpid).send(msg)

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = Intent.src_address
    msg.actions.append(of.ofp_action_output(port = links_delays[0].bw_src_port))
    core.openflow.getConnection(s5_dpid).send(msg)

    AvailableRoutes.set_available()   # Setting other available links
    intent_set = True

    # Second host
    routing_table.change_routes(s1_dpid, AvailableRoutes.Normal1_dst_address, links_delays[1].src_port)
    routing_table.change_routes(s5_dpid, AvailableRoutes.Normal1_src_address, links_delays[1].bw_src_port)
    print "Switch_1 DST address: ", AvailableRoutes.Normal1_dst_address, "  DST port: ", links_delays[1].src_port
    print "Switch_5 DST address: ", AvailableRoutes.Normal1_src_address, "  DST port: ", links_delays[1].bw_src_port

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = AvailableRoutes.Normal1_dst_address
    msg.actions.append(of.ofp_action_output(port = links_delays[1].src_port))
    core.openflow.getConnection(s1_dpid).send(msg)

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = AvailableRoutes.Normal1_src_address
    msg.actions.append(of.ofp_action_output(port = links_delays[1].bw_src_port))
    core.openflow.getConnection(s5_dpid).send(msg)

    # Third host
    routing_table.change_routes(s1_dpid, AvailableRoutes.Normal2_dst_address, links_delays[2].src_port)
    routing_table.change_routes(s5_dpid, AvailableRoutes.Normal2_src_address, links_delays[2].bw_src_port)
    print "Switch_1 DST address: ", AvailableRoutes.Normal2_dst_address, "  DST port: ", links_delays[2].src_port
    print "Switch_5 DST address: ", AvailableRoutes.Normal2_src_address, "  DST port: ", links_delays[2].bw_src_port

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = AvailableRoutes.Normal2_dst_address
    msg.actions.append(of.ofp_action_output(port = links_delays[2].src_port))
    core.openflow.getConnection(s1_dpid).send(msg)

    msg = of.ofp_flow_mod()
    msg.command=of.OFPFC_MODIFY_STRICT
    msg.priority =100
    msg.idle_timeout = 0
    msg.hard_timeout = 0
    msg.match.dl_type = 0x0800
    msg.match.nw_dst = AvailableRoutes.Normal2_src_address
    msg.actions.append(of.ofp_action_output(port = links_delays[2].bw_src_port))
    core.openflow.getConnection(s5_dpid).send(msg)
  # ***************** Setting route for Intent **************
 

  # ***************** Setting route for other connections **************
  print "Bytes received on S1-S2: ", link_s1_s2.bytes_amount
  print "Bytes received on S1-S3: ", link_s1_s3.bytes_amount
  print "Bytes received on S1-S4: ", link_s1_s4.bytes_amount

  links_delays.pop(0)   # Removing link for intent network traffic
  links_bytes = [links_delays[0], links_delays[1]]
  links_bytes.sort(key=lambda x: x.bytes_amount)

  global turn

  if not intent_set:  # If intent was set in this turn dont change other routes
    if links_delays[0].bandwidth_latency == links_bytes[0].bandwidth_latency:     # if link with lower latency has lower network traffic
      print "******** Another Routes Changed ********"
      # Second host
      x = 1
      y = 0
      if turn == 1:
        x = 0
        y = 1

      turn = 1
        
      routing_table.change_routes(s1_dpid, AvailableRoutes.Normal1_dst_address, links_delays[x].src_port)
      routing_table.change_routes(s5_dpid, AvailableRoutes.Normal1_src_address, links_delays[x].bw_src_port)
      print "Switch_1 DST address: ", AvailableRoutes.Normal1_dst_address, "  DST port: ", links_delays[x].src_port
      print "Switch_5 DST address: ", AvailableRoutes.Normal1_src_address, "  DST port: ", links_delays[x].bw_src_port

      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = AvailableRoutes.Normal1_dst_address
      msg.actions.append(of.ofp_action_output(port = links_delays[x].src_port))
      core.openflow.getConnection(s1_dpid).send(msg)

      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = AvailableRoutes.Normal1_src_address
      msg.actions.append(of.ofp_action_output(port = links_delays[x].bw_src_port))
      core.openflow.getConnection(s5_dpid).send(msg)

      # Third host
      routing_table.change_routes(s1_dpid, AvailableRoutes.Normal2_dst_address, links_delays[y].src_port)
      routing_table.change_routes(s5_dpid, AvailableRoutes.Normal2_src_address, links_delays[y].bw_src_port)
      print "Switch_1 DST address: ", AvailableRoutes.Normal2_dst_address, "  DST port: ", links_delays[y].src_port
      print "Switch_5 DST address: ", AvailableRoutes.Normal2_src_address, "  DST port: ", links_delays[y].bw_src_port

      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = AvailableRoutes.Normal2_dst_address
      msg.actions.append(of.ofp_action_output(port = links_delays[y].src_port))
      core.openflow.getConnection(s1_dpid).send(msg)

      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = AvailableRoutes.Normal2_src_address
      msg.actions.append(of.ofp_action_output(port = links_delays[y].bw_src_port))
      core.openflow.getConnection(s5_dpid).send(msg)
  # ***************** Setting route for other connections **************

  
  link_s1_s2.previous_bytes_amount = link_s1_s2.previous_bytes_amount + link_s1_s2.bytes_amount
  link_s1_s3.previous_bytes_amount = link_s1_s3.previous_bytes_amount + link_s1_s3.bytes_amount
  link_s1_s4.previous_bytes_amount = link_s1_s4.previous_bytes_amount + link_s1_s4.bytes_amount
  link_s1_s2.bytes_amount = 0
  link_s1_s3.bytes_amount = 0
  link_s1_s4.bytes_amount = 0

  measured_delay_s2 = 0.0
  measured_delay_s3 = 0.0
  measured_delay_s4 = 0.0
  measures_amount_s2 = 0
  measures_amount_s3 = 0
  measures_amount_s4 = 0


def analyze_portstats_received(switch_dpid, statistics):
  print "Bytes received on port 1:", statistics.rx_bytes, "   Bytes transmitted to port 2:", statistics.tx_bytes
  print "Packets received on port 1:", statistics.rx_packets, "   Packets transmitted to port 2:", statistics.tx_packets

def _handle_portstats_received (event):
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************
  global start_time, sent_time1, sent_time2, received_time1, received_time2
  global src_dpid, dst_dpid_s2, dst_dpid_s3, dst_dpid_s4
  global OWD1, OWD2, current_switch, link_s1_s2, link_s1_s3, link_s1_s4

  received_time = time.time() * 1000*10 - start_time

  if event.connection.dpid == src_dpid:     
    OWD1=0.5*(received_time - sent_time1)   #measure T1 as of lab guide
  elif event.connection.dpid == dst_dpid_s2 and current_switch == SWITCH2_WORKING:   
    OWD2=0.5*(received_time - sent_time2)   #measure T2 as of lab guide
  elif event.connection.dpid == dst_dpid_s3 and current_switch == SWITCH3_WORKING:
    OWD2=0.5*(received_time - sent_time2)
  elif event.connection.dpid == dst_dpid_s4 and current_switch == SWITCH4_WORKING:
    OWD2=0.5*(received_time - sent_time2)
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************

  #Observe the handling of port statistics provided by this function.
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global s1_p1,s1_p4, s1_p5, s1_p6, s2_p1, s3_p1, s4_p1
  global pre_s1_p1,pre_s1_p4, pre_s1_p5, pre_s1_p6, pre_s2_p1, pre_s3_p1, pre_s4_p1

  if event.connection.dpid==s1_dpid: # The DPID of one of the switches involved in the link
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s1_p1=s1_p1
          s1_p1=f.rx_packets
          #print "s1_p1->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==4:
          pre_s1_p4=s1_p4
          s1_p4=f.tx_packets
          #s1_p4=f.tx_bytes
          #print "s1_p4->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==5:
          pre_s1_p5=s1_p5
          s1_p5=f.tx_packets
        if f.port_no==6:
          pre_s1_p6=s1_p6
          s1_p6=f.tx_packets
 
  if event.connection.dpid==s2_dpid:
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s2_p1=s2_p1
          s2_p1=f.rx_packets
           #s2_p1=f.rx_bytes
           # analyze_portstats_received(s2_dpid, f)
        if f.port_no == 1:
          link_s1_s2.bytes_amount = f.rx_bytes - link_s1_s2.previous_bytes_amount
    print getTheTime(), "s1_p4(Sent):", (s1_p4-pre_s1_p4), "s2_p1(Received):", (s2_p1-pre_s2_p1)
 
  if event.connection.dpid==s3_dpid:
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s3_p1=s3_p1
          s3_p1=f.rx_packets
        if f.port_no == 1:
          link_s1_s3.bytes_amount = f.rx_bytes - link_s1_s3.previous_bytes_amount
    print getTheTime(), "s1_p5(Sent):", (s1_p5-pre_s1_p5), "s3_p1(Received):", (s3_p1-pre_s3_p1)

  if event.connection.dpid==s4_dpid:
    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s4_p1=s4_p1
          s4_p1=f.rx_packets
        if f.port_no == 1:
          link_s1_s4.bytes_amount = f.rx_bytes - link_s1_s4.previous_bytes_amount
    print getTheTime(), "s1_p6(Sent):", (s1_p6-pre_s1_p6), "s4_p1(Received):", (s4_p1-pre_s4_p1)

def _handle_ConnectionUp (event):
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************
  global src_dpid, dst_dpid, mytimer
  global link_s1_s2, link_s1_s3, link_s1_s4
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************


  # waits for connections from all switches, after connecting to all of them it starts a round robin timer for triggering h1-h4 routing changes
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global src_dpid, dst_dpid_s2, dst_dpid_s3, dst_dpid_s4
  global routing_table

  print "ConnectionUp: ",dpidToStr(event.connection.dpid)
 
  #remember the connection dpid for the switch
  for m in event.connection.features.ports:
    if m.name == "s1-eth1":
      # s1_dpid: the DPID (datapath ID) of switch s1;
      s1_dpid = event.connection.dpid
      src_dpid = event.connection.dpid
      print "s1_dpid=", s1_dpid
    elif m.name == "s2-eth1":
      s2_dpid = event.connection.dpid
      dst_dpid_s2 = event.connection.dpid
      print "s2_dpid=", s2_dpid
    elif m.name == "s3-eth1":
      s3_dpid = event.connection.dpid
      dst_dpid_s3 = event.connection.dpid
      print "s3_dpid=", s3_dpid
    elif m.name == "s4-eth1":
      s4_dpid = event.connection.dpid
      dst_dpid_s4 = event.connection.dpid
      print "s4_dpid=", s4_dpid
    elif m.name == "s5-eth1":
      s5_dpid = event.connection.dpid
      print "s5_dpid=", s5_dpid

  if s1_dpid<>0 and s2_dpid<>0 and s3_dpid<>0 and s4_dpid<>0 and s5_dpid<>0:
    link_s1_s2 = Link(s1_dpid, s2_dpid, 4, 1)
    link_s1_s3 = Link(s1_dpid, s3_dpid, 5, 2)
    link_s1_s4 = Link(s1_dpid, s4_dpid, 6, 3)
    Intent.change_intent(1)
    routing_table = RoutingTable(s1_dpid, s5_dpid)

    Timer(0.5, measure_delays, recurring=True)
    Timer(32, set_routing, recurring=True)
    Timer(60, switch_intent, recurring=True)
 
def _handle_PacketIn(event):
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************
  #This function is called to handle PACKET_IN messages received by the controller
  
  global start_time, OWD1, OWD2, current_switch, routing_table
  global measured_delay_s2, measured_delay_s3, measured_delay_s4
  global measures_amount_s2, measures_amount_s3, measures_amount_s4
  global measures_mean_s2, measures_mean_s3, measures_mean_s4

  packet = event.parsed

  if packet.type==0x5577 and (event.connection.dpid==dst_dpid_s2 or event.connection.dpid==dst_dpid_s3 or event.connection.dpid==dst_dpid_s4): #0x5577 is unregistered EtherType, here assigned to probe packets
    received_time = time.time() * 1000*10 - start_time #amount of time elapsed from start_time
    
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    delay = int(received_time - d - OWD1 - OWD2)/10

    if(current_switch == SWITCH2_WORKING):
      # print "Delay on link S1 - S2"
      current_switch = SWITCH3_READY
      measured_delay_s2 += delay
      measures_amount_s2 += 1
    elif(current_switch == SWITCH3_WORKING):
      # print "Delay on link S1 - S3"
      current_switch = SWITCH4_READY
      measured_delay_s3 += delay
      measures_amount_s3 += 1
    elif(current_switch == SWITCH4_WORKING):
      # print "Delay on link S1 - S4"
      current_switch = SWITCH2_READY
      measured_delay_s4 += delay
      measures_amount_s4 += 1
    
    # print "[ms*10]: received_time=", int(received_time), ", d=", d, ", OWD1=", int(OWD1), ", OWD2=", int(OWD2)
    # print "delay:", delay, "[ms] <=====" # divide by 10 to normalise to milliseconds
    return # It is important to analyze only this part when using probe packet, because below code works only for standard packets
  #******************************************************************************************************************************************
  #******************************************************************************************************************************************

  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid

  packet=event.parsed
  #print "_handle_PacketIn is called, packet.type:", packet.type, " event.connection.dpid:", event.connection.dpid

  # Below, set the default/initial routing rules for all switches and ports.
  # All rules are set up in a given switch on packet_in event received from the switch which means no flow entry has been found in the flow table.
  # This setting up may happen either at the very first pactet being sent or after flow entry expirationn inn the switch
  if event.connection.dpid==s1_dpid:
     a=packet.find('arp')					# If packet object does not encapsulate a packet of the type indicated, find() returns None
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)			# Create packet_out message; use the incoming packet as the data for the packet out
       msg.actions.append(of.ofp_action_output(port=4))		# Add an action to send to the specified port
       event.connection.send(msg)				# Send message to switch
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800		# rule for IP packets (x0800)
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.1"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.2"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.3"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 1
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.4"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.5"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch1["10.0.0.6"]))
     event.connection.send(msg)
 
  elif event.connection.dpid==s2_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806		# rule for ARP packets (x0806)
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s3_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
  
  elif event.connection.dpid==s4_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s5_dpid: 
     a=packet.find('arp')
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=4))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.1"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.2"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.3"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.4"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.5"]))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = routing_table.switch5["10.0.0.6"]))
     event.connection.send(msg)

#As usually, launch() is the function called by POX to initialize the component (routing_controller.py in our case) 
#indicated by a parameter provided to pox.py 

def launch ():
  global start_time, current_switch
  start_time = time.time() * 1000*10
  # current_switch = SWITCH2_READY
  # core is an instance of class POXCore (EventMixin) and it can register objects.
  # An object with name xxx can be registered to core instance which makes this object become a "component" available as pox.core.core.xxx.
  # for examples see e.g. https://noxrepo.github.io/pox-doc/html/#the-openflow-nexus-core-openflow 
  core.openflow.addListenerByName("PortStatsReceived",_handle_portstats_received) # listen for port stats , https://noxrepo.github.io/pox-doc/html/#statistics-events
  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp) # listen for the establishment of a new control channel with a switch, https://noxrepo.github.io/pox-doc/html/#connectionup
  core.openflow.addListenerByName("PacketIn",_handle_PacketIn) # listen for the reception of packet_in message from switch, https://noxrepo.github.io/pox-doc/html/#packetin

