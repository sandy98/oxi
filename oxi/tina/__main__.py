# -*-  coding: utf_8 -*-

import os, asyncio

root_dir = os.path.split(__file__)[0]
curr_dir = os.getcwd()
parent_dir = os.path.split(curr_dir)[0]
static_dir = os.path.split(curr_dir)[1]

# os.chdir(root_dir)
# os.sys.path.append(root_dir)

# try:
#     activate_this = f'{root_dir}/bin/activate_this.py'
#     with open(activate_this, "r") as activate_this_fp:
#         exec(activate_this_fp.read(), dict(__file__=activate_this))
# except:
#     pass

try:
    from tina.tinaserver import TinaHandler, run_dev_server, tina_port, static_app as app
except:
    from tinaserver import TinaHandler, run_dev_server, tina_port, static_app as app

TinaHandler.load_config()
TinaHandler.config['static-dir'] = static_dir
os.chdir(curr_dir)
port = tina_port
if len(os.sys.argv) > 1 and os.sys.argv[1].isdigit():
    port = int(os.sys.argv[1])
try:
    # print(f"\nTina Server serving demo Tina App at port {tina_port}\n")
    asyncio.run(run_dev_server(app, host='0.0.0.0', port=port))
except KeyboardInterrupt:
    print("Tina leaves the stage...\nBye, bye.")
    os.sys.exit(0)
    
