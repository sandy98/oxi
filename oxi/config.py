# -*- coding: utf-8 -*-

import os, json

Config = {
    'static_dir': 'static',
    'template_dir': 'templates',
    'upload_dir': 'uploads',
    'log_dir': 'logs',
    'cgi_dir': 'cgi-bin',
    'allow_dirlisting': True,
    'allow_cgi': True,
    'chunk_size': 8192,
    'index_files': ['index.html', 'index.htm'],
}

if os.path.exists('config.json'):
    with open('config.json', 'r') as fd:
        file_config = json.load(fd)
        Config.update(file_config)
else:
    with open('config.json', 'w') as fd:
        json.dump(Config, fd, 
                  indent=4, separators=(",", ": "), 
                  ensure_ascii=False, sort_keys=True)
