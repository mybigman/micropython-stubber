# create stubs for (all) modules on a MicroPython board
# ref: https://github.com/thonny/thonny/blob/786f63ff4460abe84f28c14dad2f9e78fe42cc49/thonny/plugins/micropython/__init__.py#L608
# pylint: disable=bare-except
import errno
import gc
import logging
import os
from time import sleep_us
from ujson import dumps

stubber_version = '1.0.1'
# deal with firmware specific implementations
try:
    from machine import resetWDT
except:
    def resetWDT():
        pass

class Stubber():
    "Generate stubs for (hopefully) all modules in the firmware"
    def __init__(self, path: str = None):
        # log = logging.getLogger(__name__)
        self._log = logging.getLogger('Stubber')
        self._report = []
        u = os.uname()
        self._report.append({'sysname': u.sysname, 'nodename': u.nodename, 'release': u.release, 'version': u.version, 'machine': u.machine})
        self._report.append({'stubber': stubber_version})
        if path is None:
            #determine path for stubs
            path = "{}/stubs/{}".format(
                self.get_root(),
                self.firmware_ID(asfile=True)
                ).replace('//', '/')            
        else:
            #get rid of trailing slash
            if path.endswith('/'):
                path = path[:-1]

        self.path = path
        try:
            self.ensure_folder(path + "/")
        except:
            self._log.error("error creating stub folder %s" % path)

        self.problematic = ["upysh", "webrepl_setup", "http_client", "http_client_ssl", "http_server", "http_server_ssl"] 
        self.excluded = ["webrepl", "_webrepl", "webrepl_setup"]
        # there is no option to discover modules from upython, need to hardcode
        # below contains the combines modules from  Micropython ESP8622, ESP32 and Loboris Modules
        self.modules = ['_boot', '_onewire', '_thread', '_webrepl', 'ak8963', 'apa102', 'apa106', 'array', 'binascii', 'btree', 'builtins',
                        'cmath', 'collections', 'curl', 'dht', 'display', 'ds18x20', 'errno', 'esp', 'esp32', 'example_pub_button', 'example_sub_led',
                        'flashbdev', 'framebuf', 'freesans20', 'functools', 'gc', 'gsm', 'hashlib', 'heapq', 'http_client', 'http_client_ssl', 'http_server',
                        'http_server_ssl', 'inisetup', 'io', 'json', 'logging', 'lwip', 'machine', 'math', 'microWebSocket', 'microWebSrv', 'microWebTemplate',
                        'micropython', 'mpu6500', 'mpu9250', 'neopixel', 'network', 'ntptime', 'onewire', 'os', 'port_diag', 'pye', 'random', 're', 'requests',
                        'select', 'socket', 'socketupip', 'ssd1306', 'ssh', 'ssl', 'struct', 'sys', 'time', 'tpcalib', 'uasyncio/__init__', 'uasyncio/core', 'ubinascii',
                        'ucollections', 'ucryptolib', 'uctypes', 'uerrno', 'uhashlib', 'uheapq', 'uio', 'ujson', 'umqtt/robust', 'umqtt/simple', 'uos', 'upip', 'upip_utarfile',
                        'upysh', 'urandom', 'ure', 'urequests', 'urllib/urequest', 'uselect', 'usocket', 'ussl', 'ustruct', 'utime', 'utimeq', 'uwebsocket', 'uzlib', 'webrepl',
                        'webrepl_setup', 'websocket', 'websocket_helper', 'writer', 'ymodem', 'zlib']

    def get_obj_attribs(self, obj: object):
        result = []
        errors = []
        #self._log.info('get attributes {} {}'.format(repr(obj),obj ))
        for name in dir(obj):
            try:
                val = getattr(obj, name)
                # name , value , type
                result.append((name, repr(val), repr(type(val)), val))
                #self._log.info( result[-1])
            except BaseException as e:
                errors.append("Couldn't get attribute '{}' from object '{}', Err: {}".format(name, obj, e))
        gc.collect()
        return result, errors

    def add_modules(self, modules :list):
        "Add additional modules to be exported"
        self.modules = sorted(set(self.modules) | set(modules))
    
    def generate_all_stubs(self):
        try:
            for module_name in sorted(self.modules):
                if not module_name.startswith("_"):
                    file_name = "{}/{}.py".format(
                        self.path,
                        module_name.replace(".", "/")
                    )
                    self._log.info("dump module: {:<20} to file: {}".format(module_name, file_name))
                    self.dump_module_stub(module_name, file_name)
        finally:
            self._log.info('Finally done')

    # Create a Stub of a single python module
    def dump_module_stub(self, module_name: str, file_name: str = None):
        if module_name.startswith("_") and module_name != '_thread':
            self._log.warning("SKIPPING internal module:{}".format(module_name))
            return

        if module_name in self.problematic:
            self._log.warning("SKIPPING problematic module:{}".format(module_name))
            return

        if '/' in module_name:
            #for nested modules
            self.ensure_folder(file_name)
            module_name = module_name.replace('/', '.')
            self._log.warning("SKIPPING nested module:{}".format(module_name))
            return

        if file_name is None:
            file_name = module_name.replace('.', '_') + ".py"

        #import the module (as new_module) to examine it
        try:
            new_module = __import__(module_name)
        except ImportError as e:
            self._log.debug("Unable to import module: {} : {}".format(module_name, e))
            return 
        except e:
            self._log.error("Failed to import Module: {}".format(module_name))

            return 

        # Start a new file
        with open(file_name, "w") as fp:
            s = "\"\"\"\nModule: '{0}' on {1}\n\"\"\"\n# MCU: {2}\n# Stubber: {3}\n".format(module_name, self.firmware_ID(), os.uname(), stubber_version)
            fp.write(s)
            if module_name not in self.excluded:
                self._dump_object_stubs(fp, new_module, module_name, "")
                self._report.append({"module":module_name, "file": file_name})
            else:
                self._log.warning("skipped excluded module {}".format(module_name))

        if not module_name in ["os", "sys", "logging", "gc"]:
            #try to unload the module unless we use it
            try:
                del new_module
            except BaseException:
                self._log.warning("could not unload module {}".format(module_name))
            finally:
                gc.collect()

    def _dump_object_stubs(self, fp, object_expr: object, obj_name: str, indent: str):
        if object_expr in self.problematic:
            self._log.warning("SKIPPING problematic module:{}".format(object_expr))
            return

        self._log.debug("DUMPING : {}".format(object_expr))
        items, errors = self.get_obj_attribs(object_expr)
        if errors:
            self._log.error(errors)

        for name, rep, typ, obj in sorted(items, key=lambda x: x[0]):
            if name.startswith("__"):
                #skip internals
                continue
            # allow the scheduler to run
            resetWDT()
            sleep_us(1)

            # self._log.debug("DUMPING", indent, object_expr, name)
            self._log.debug("  * " + name + " : " + typ)

            if typ in ["<class 'function'>", "<class 'bound_method'>"]:
                s = indent + "def " + name + "():\n"
                s += indent + "    pass\n\n"
                fp.write(s)
                self._log.debug(s)

            elif typ in ["<class 'str'>", "<class 'int'>", "<class 'float'>"]:
                s = indent + name + " = " + rep + "\n"
                fp.write(s)
                self._log.debug(s)
            #new class
            elif typ == "<class 'type'>" and indent == "":
                # full expansion only on toplevel
                # stub style : ...
                # s = "\n{}class {}(): ...\n".format(indent, name)
                # stub style : Empty comment ... + hardcoded 4 spaces
                s = "\n" + indent + "class " + name + ":\n"  # What about superclass?
                s += indent + "    ''\n"

                fp.write(s)
                self._log.debug(s)

                self._log.debug("#recursion !!")
                self._dump_object_stubs(fp, obj, "{0}.{1}".format(obj_name, name), indent + "    ")
            else:
                # keep only the name
                fp.write(indent + name + " = None\n")

    @staticmethod
    def firmware_ID(asfile: bool = False):
        if os.uname().sysname in 'esp32_LoBo':
            #version in release
            ver = os.uname().release
        else:
            # version before '-' in version
            ver = os.uname().version.split('-')[0]
        fid = "{} {}".format(os.uname().sysname, ver)
        if asfile:
            # path name restrictions
            chars = " .()/\\:$"
            for c in chars:
                fid = fid.replace(c, "_")
        return fid

    def clean(self):
        "Remove all files from the stub folder"
        print("Clean/remove files in stubfolder: {}".format(self.path))
        for fn in os.listdir(self.path):
            try:
                os.remove("{}/{}".format(self.path, fn))
            except:
                pass

    def report(self, filename: str = "modules.json"):
        "create json with list of exported modules"
        print("Created stubs for {} modules on board {} - {}\nPath: {}".format(
            len(self._report)-2,
            os.uname().machine,
            os.uname().release,
            self.path
            ))
        f_name = "{}/{}".format(self.path, filename)
        gc.collect()
        try:
            # write json by node to reduce memory requirements
            with open(f_name, 'w') as f:
                start = True
                for n in self._report:
                    if start:
                        f.write('[')
                        start = False
                    else:
                        f.write(',')
                    f.write(dumps(n))
                f.write(']')
        except:
            print("Failed to create the report.")

    def ensure_folder(self, path: str):
        "create nested folders if needed"
        i = start = 0
        while i != -1:
            i = path.find('/', start)
            if i != -1:
                if i == 0:
                    p = path[0]
                else:
                    p = path[0:i]
                # p = partial folder
                try:
                    _ = os.stat(p)
                except OSError as e:
                    # folder does not exist
                    if e.args[0] == errno.ENOENT:
                        try:
                            os.mkdir(p)
                        except OSError as e2:
                            self._log.error('failed to create folder {}'.format(p))
                            raise e2
                    else:
                        self._log.error('failed to create folder {}'.format(p))
                        raise e
            #next level deep
            start = i+1

    @staticmethod
    def get_root():
        "Determine the root folder of the device"
        try:
            r = "/flash"
            _ = os.stat(r)
        except OSError as e:
            if e.args[0] == errno.ENOENT:
                r = os.getcwd()
            else:
                r = '/'
        return r


def main():
    logging.basicConfig(level=logging.INFO)

    # Now clean up and get to work
    stubber = Stubber()
    #stubber.add_modules(['xyz'])
    stubber.clean()
    stubber.generate_all_stubs()
    stubber.report()

main()
