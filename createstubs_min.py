"""
Create stubs for (all) modules on a MicroPython board
Copyright (c) 2019 Jos Verlinde
"""
import errno
import gc
import os
import sys
from utime import sleep_us
from ujson import dumps
stubber_version='1.2.0'
try:
 from machine import resetWDT
except:
 def resetWDT():
  pass
class Stubber():
 def __init__(self,path:str=None):
  self._report=[]
  u=os.uname()
  v=".".join([str(i)for i in sys.implementation.version])
  self._report_fwi={'firmware':{'sysname':u.sysname,'nodename':u.nodename,'release':u.release,'version':v,'machine':u.machine,'firmware':self.firmware_ID()}}
  self._report_stb={'stubber':{'version':stubber_version}}
  del u
  del v
  if path:
   if path.endswith('/'):
    path=path[:-1]
  else:
   path="{}/stubs/{}".format(self.get_root(),self.firmware_ID(asfile=True)).replace('//','/')
  self.path=path
  try:
   self.ensure_folder(path+"/")
  except:
   pass
  self.problematic=["upysh","webrepl_setup","http_client","http_client_ssl","http_server","http_server_ssl"]
  self.excluded=["webrepl","_webrepl","webrepl_setup"]
  self.modules=['_boot','_onewire','_thread','_webrepl','ak8963','apa102','apa106','array','binascii','btree','builtins','upip','cmath','collections','curl','dht','display','ds18x20','errno','esp','esp32','example_pub_button','example_sub_led','flashbdev','framebuf','freesans20','functools','gc','gsm','hashlib','heapq','http_client','http_client_ssl','http_server','http_server_ssl','inisetup','io','json','logging','lwip','machine','math','microWebSocket','microWebSrv','microWebTemplate','micropython','mpu6500','mpu9250','neopixel','network','ntptime','onewire','os','port_diag','pye','random','re','requests','select','socket','socketupip','ssd1306','ssh','ssl','struct','sys','time','tpcalib','uasyncio','uasyncio/core','ubinascii','ucollections','ucryptolib','uctypes','uerrno','uhashlib','uheapq','uio','ujson','umqtt/robust','umqtt/simple','uos','upip_utarfile','upysh','urandom','ure','urequests','urllib/urequest','uselect','usocket','ussl','ustruct','utime','utimeq','uwebsocket','uzlib','webrepl','webrepl_setup','websocket','websocket_helper','writer','ymodem','zlib']
  self.include_nested=gc.mem_free()>3200
 def get_obj_attributes(self,obj:object):
  result=[]
  errors=[]
  for name in dir(obj):
   try:
    val=getattr(obj,name)
    result.append((name,repr(val),repr(type(val)),val))
   except BaseException as e:
    errors.append("Couldn't get attribute '{}' from object '{}', Err: {}".format(name,obj,e))
  gc.collect()
  return result,errors
 def add_modules(self,modules:list):
  self.modules=sorted(set(self.modules)|set(modules))
 def create_all_stubs(self):
  self.modules=[m for m in self.modules if '/' in m]+[m for m in self.modules if '/' not in m]
  gc.collect()
  for module_name in self.modules:
   if self.include_nested:
    self.include_nested=gc.mem_free()>3200
   if module_name.startswith("_")and module_name!='_thread':
    continue
   if module_name in self.problematic:
    continue
   if module_name in self.excluded:
    continue
   file_name="{}/{}.py".format(self.path,module_name.replace(".","/"))
   gc.collect()
   m1=gc.mem_free()
   print("Stub module: {:<20} to file: {:<55} mem:{:>5}".format(module_name,file_name,m1))
   try:
    self.create_module_stub(module_name,file_name)
   except:
    pass
   gc.collect()
   m2=gc.mem_free()
 def create_module_stub(self,module_name:str,file_name:str=None):
  if module_name.startswith("_")and module_name!='_thread':
   return
  if module_name in self.problematic:
   return
  if '/' in module_name:
   self.ensure_folder(file_name)
   module_name=module_name.replace('/','.')
   if not self.include_nested:
    return
  if file_name is None:
   file_name=module_name.replace('.','_')+".py"
  try:
   new_module=__import__(module_name)
  except ImportError as e:
   return
  except e:
   return
  with open(file_name,"w")as fp:
   s="\"\"\"\nModule: '{0}' on {1}\n\"\"\"\n# MCU: {2}\n# Stubber: {3}\n".format(module_name,self.firmware_ID(),os.uname(),stubber_version)
   fp.write(s)
   self.write_object_stub(fp,new_module,module_name,"")
   self._report.append({"module":module_name,"file":file_name})
  if not module_name in["os","sys","logging","gc"]:
   try:
    del new_module
   except BaseException:
    pass
   try:
    del sys.modules[module_name]
   except BaseException:
    pass
   gc.collect()
 def write_object_stub(self,fp,object_expr:object,obj_name:str,indent:str):
  if object_expr in self.problematic:
   return
  items,errors=self.get_obj_attributes(object_expr)
  for name,rep,typ,obj in sorted(items,key=lambda x:x[0]):
   if name.startswith("__"):
    continue
   resetWDT()
   sleep_us(1)
   if typ in["<class 'function'>","<class 'bound_method'>"]:
    s=indent+"def "+name+"():\n"
    s+=indent+"    pass\n\n"
    fp.write(s)
   elif typ in["<class 'str'>","<class 'int'>","<class 'float'>"]:
    s=indent+name+" = "+rep+"\n"
    fp.write(s)
   elif typ=="<class 'type'>" and indent=="":
    s="\n"+indent+"class "+name+":\n" 
    s+=indent+"    ''\n"
    fp.write(s)
    self.write_object_stub(fp,obj,"{0}.{1}".format(obj_name,name),indent+"    ")
   else:
    fp.write(indent+name+" = None\n")
  del items
  del errors
  try:
   del name,rep,typ,obj 
  except:
   pass
 @staticmethod
 def firmware_ID(asfile:bool=False):
  if os.uname().sysname in 'esp32_LoBo':
   ver=os.uname().release
  else:
   ver=os.uname().version.split('-')[0]
  fid="{} {}".format(os.uname().sysname,ver)
  if asfile:
   chars=" .()/\\:$"
   for c in chars:
    fid=fid.replace(c,"_")
  return fid
 def clean(self):
  for fn in os.listdir(self.path):
   try:
    os.remove("{}/{}".format(self.path,fn))
   except:
    pass
 def report(self,filename:str="modules.json"):
  f_name="{}/{}".format(self.path,filename)
  gc.collect()
  try:
   with open(f_name,'w')as f:
    f.write('{')
    f.write(dumps(self._report_fwi)[1:-1])
    f.write(',')
    f.write(dumps(self._report_stb)[1:-1])
    f.write(',')
    f.write('"modules" :[')
    start=True
    for n in self._report:
     if start:
      start=False
     else:
      f.write(',')
     f.write(dumps(n))
    f.write(']}')
  except:
   pass
 def ensure_folder(self,path:str):
  i=start=0
  while i!=-1:
   i=path.find('/',start)
   if i!=-1:
    if i==0:
     p=path[0]
    else:
     p=path[0:i]
    try:
     _=os.stat(p)
    except OSError as e:
     if e.args[0]==errno.ENOENT:
      try:
       os.mkdir(p)
      except OSError as e2:
       raise e2
     else:
      raise e
   start=i+1
 @staticmethod
 def get_root():
  try:
   r="/flash"
   _=os.stat(r)
  except OSError as e:
   if e.args[0]==errno.ENOENT:
    r=os.getcwd()
   else:
    r='/'
  return r
def main():
 global stubber
 try:
  logging.basicConfig(level=logging.INFO)
 except:
  pass
 stubber=Stubber()
 stubber.clean()
 stubber.create_all_stubs()
 stubber.report()
main()