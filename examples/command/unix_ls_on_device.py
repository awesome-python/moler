from moler.config import load_config
from moler.device.device import DeviceFactory

load_config(path='my_devices.yml')

my_unix = DeviceFactory.get_device(name='RebexTestMachine')
my_unix.goto_state(state="UNIX_REMOTE")

ls_cmd = my_unix.get_cmd(cmd_name="ls", cmd_params={"options": "-l"})
ls_cmd.connection.newline = '\r\n'  # tweak since remote console uses such one

remote_files = ls_cmd()

if 'readme.txt' in remote_files['files']:
    print("readme.txt file:")
    readme_file_info = remote_files['files']['readme.txt']
    for attr in readme_file_info:
        print("  {:<18}: {}".format(attr, readme_file_info[attr]))

"""
readme.txt file:
  permissions       : -rw-------
  hard_links_count  : 1
  owner             : demo
  group             : users
  size_raw          : 403
  size_bytes        : 403
  date              : Apr 08  2014
  name              : readme.txt
"""
