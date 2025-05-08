#!/usr/bin/env python
# -*- coding: utf_8 -*-

# test with: static/Media/Videos/Cele/Cele_patinando_cerca_de_Venecia.mp4

import os, mmap, asyncio
from mimetypes import guess_type
import argparse #, copy
from . import __version__ as oxi_version
from .utils import dual_mode
       
class Smmap:
    def __init__(self, fileno, offset:int = 0, limit:int =  0):
        self._mmap = mmap.mmap(fileno, 0, flags=mmap.MAP_PRIVATE)
        self._offset = offset
        self._limit = limit
        self._mmap.seek(self._offset)

    def __getitem__(self, index):
        shifted_index = None
        if isinstance(index, slice):
            indexstart = 0 if not index.start else index.start
            indexstop = len(self._mmap) if not index.stop else index.stop
            indexstart = 0 if indexstart < 0 else indexstart
            indexstart = self._limit if indexstart > self._limit else indexstart
            indexstop = 0 if indexstop < 0 else indexstop
            indexstop = self._limit if indexstop > self._limit else indexstop
            shifted_index = slice(indexstart + self._offset, indexstop + self._offset, index.step)
        else:
            shifted_index = index
            shifted_index = 0 if shifted_index < 0 else shifted_index
            shifted_index = self._limit if shifted_index > self._limit else shifted_index
            shifted_index += self._offset
        return self._mmap.__getitem__(shifted_index)
    
    def __setitem__(self, index, value):
        shifted_index = None
        if isinstance(index, slice):
            indexstart = 0 if not index.start else index.start
            indexstop = len(self._mmap) if not index.stop else index.stop
            indexstart = 0 if indexstart < 0 else indexstart
            indexstart = self._limit if indexstart > self._limit else indexstart
            indexstop = 0 if indexstop < 0 else indexstop
            indexstop = self._limit if indexstop > self._limit else indexstop
            diff = indexstop - indexstart
            if not isinstance(value, bytes) or len(value) > diff:
                raise ValueError(f"value must be an instance of bytes with len <= to {diff}")
            for i in range(diff):
                self._mmap[indexstart + i + self._offset] = value[i]
        else:
            shifted_index = index
            shifted_index = 0 if shifted_index < 0 else shifted_index
            shifted_index = self._limit if shifted_index > self._limit else shifted_index
            shifted_index += self._offset
            self._mmap[shifted_index], = value
    
    @property
    def size(self):
        return self._limit
    
    @property
    def offset(self):
        return self._offset
    
    @property
    def mmap(self):
        return self._mmap
    
    def seek(self, num: int):
        num = self._limit if num >= self._limit else num
        self._mmap.seek(num + self._offset)

    def tell(self):
        return self._mmap.tell() - self._offset

    def read(self, nbytes: int = -1):
        if nbytes == -1 or nbytes >= (self._limit - self.tell()):
            nbytes = self._limit - self.tell()
        return self._mmap.read(nbytes)
    
    def write(self, what: bytes = b''):
        self._mmap.write(what)

    def find(self, what: bytes):
        found = self._mmap.find(what)
        return found if found == -1 else found - self._offset

    def rfind(self, what: bytes):
        found = self._mmap.rfind(what)
        return found if found == -1 else found - self._offset

    def close(self):
        self._mmap.close()

    def __del__(self):
        try:
            if not self._mmap.closed:
                self._mmap.close()
        except:
            pass


class Mp4:
    """Stub for Atom"""

class Atom:
    def __init__(self, offset: int, size: int, name: str, level: int = 0, ordinal: int = -1, container=None):
        self.offset = offset
        self.size = size
        self.name = name
        self.ordinal = ordinal
        self.level = level
        # self.contents = contents
        self.container = container
        self.children: list = []
        self._mm = None

    @property
    def contents(self):
        if self._mm:
            return self._mm
        if not self.container:
            return None
        fp = self.container.fp
        if not fp:
            return None
        self._mm = Smmap(fp.fileno(), self.offset, self.size)
        return self._mm

    def setcontents(self, new_mm):
        self._mm = new_mm

    def __repr__(self):
        # Atom ftyp @ 0 of size: 32, ends @ 32
        args = ('\t' * self.level, self.name, f"{self.offset:,}", f"{self.size:,}", f"{(self.offset + self.size):,}")
        return "{0}Atom {1} @ {2} of size: {3} , ends @ {4}".format(*args)


    def __str__(self):
        mainline = repr(self)
        lenchildren = len(self.children) if self.children else 0
        childrenlines = ''.join(map(str, self.children)) if lenchildren else ''
        return "\n".join([mainline, childrenlines])

    def load_contents(self, fp = None):
        # Retained for backward compatibility
        pass

    def load_children(self):
            container: Mp4 = self.container
            ordinal = 0
            offset = self.offset + 8
            fp = mmap.mmap(container.fp.fileno(), container.filesize, flags=mmap.MAP_PRIVATE)
            while offset < (self.size + self.offset):
                child = container._get_atom(fp, offset, ordinal, self.level + 1)
                if child.size == 0:
                    raise ValueError("Atom of size 0 not admitted out of 0 level.")
                if child.offset + child.size > container.filesize:
                    raise ValueError("Atom size exceeds file boundaries.")
                if child.name == '\x00\x00\x00\x00':
                    offset += child.size
                    continue
                if child.name in ["trak", "mdia", "minf", "stbl"]:
                    # Known ancestor atom of stco or co64, search within it!
                    # for res in _find_atoms_ex(atom, datastream):
                    #     yield res
                    child.load_children()
                elif child.name in ["stco", "co64"]:
                    self.container.relocation_targets.append(child)
                self.children.append(child)
                ordinal += 1
                offset += child.size
          
    @property
    def boundaries(self):
        return [self.offset, self.offset + self.size]
    
    @property
    def named_boundaries(self):
        return {self.name: self.boundaries}


class Mp4:
    def __init__(self, filename):
        if not os.path.exists(filename):
            raise NameError(f"File {filename} doesn't exist.")
        if guess_type(filename)[0] not in ['video/mp4', 'video/quicktime']:
            raise TypeError(f"File {filename} is not an MP4 file.")
        self.filename = filename
        self.filesize = os.path.getsize(filename)
        self.loop = None
        self.atoms: list[Atom] = []
        self.relocation_targets: list[Atom] = []
        self.ftyp: Atom = None
        self.moov: Atom = None
        self.free: Atom = None
        self.mdat: Atom = None
        self._patched_moov: bytearray = None
        self.fp = open(self.filename, 'rb')
        self.atoms = self._collectatoms()

    def __del__(self):
        try:
            if not self.fp.closed:
                self.fp.close()
        except:
            pass

    def __str__(self):
        atomstrs = "\n".join(list(map(lambda a: "   " + str(a), self.atoms)))
        return f"""

{'_' * 80}

File: {self.filename}
Size: {self.filesize:,}
{'_' * 80}

{atomstrs}

{'_' * 80}
"""

    def __repr__(self):
        return "\n".join(self.quicklist())
    
    def _get_atom(self, fp: mmap.mmap, offset: int, ordinal: int=0, level:int=0):
        size, name = [int.from_bytes(fp[offset:offset+4], byteorder='big'), fp[offset+4:offset+8].decode('latin-1')]
        if size == 1:
            size = int.from_bytes(fp[offset+8:offset+16], byteorder='big')
        atom = Atom(offset=offset, size=size, name=name, level=level, ordinal = ordinal, container=self)
        return atom
    
    def _parse_mp4(self):
        filesize = self.filesize
        with mmap.mmap(self.fp.fileno(), filesize, flags=mmap.MAP_PRIVATE) as fp:
            ordinal = 0
            offset = 0
            while offset < filesize:
                atom = self._get_atom(fp, offset, ordinal, 0)
                if atom.size == 0:
                    atom.size = self.filesize - offset
                    yield atom
                    return
                ordinal += 1
                offset += atom.size
                if atom.name != '\x00\x00\x00\x00':
                    yield atom
                else:
                    continue

    def _collectatoms(self):
        atoms = [self._classify_atom(atom) for atom in self._parse_mp4()]
        # if self.moov:
        #     self.moov.load_children()
        return atoms
    
    def _is_relocatable(self):
        return (not not self.moov) and (not self._is_compressed()) and (self.moov.ordinal > self.mdat.ordinal)
    
    def _patch_moov(self):
        if self._patched_moov is not None or not self.moov or self._is_compressed():
            return
        offset_shift = self.moov.size
        self.moov.contents.seek(0)
        self._patched_moov = mmap.mmap(-1, self.moov.size)
        self._patched_moov.write(self.moov.contents.read())
        for atom in self.relocation_targets:
            # os.sys.stderr.write(f'{atom.name} located at ' + str(atom.offset) + '\n')
            # os.sys.stderr.flush()
            offset_pos_begin = atom.offset - self.moov.offset
            offset_pos = offset_pos_begin
            entry_count = int.from_bytes(self._patched_moov[offset_pos+12:offset_pos+16], byteorder='big')
            # print(f"Patching atom '{atom.name}' with {entry_count} entries.")
            displacement = 4 if atom.name == 'stco' else 8 # in case atom.name == 'co64'
            for i in range(entry_count):
                offset_pos = offset_pos_begin + 16 + (i * displacement)
                current_offset = int.from_bytes(self._patched_moov[offset_pos:offset_pos+4], byteorder='big')
                new_offset = current_offset + offset_shift
                # print(f"{i}: Transferring offset {current_offset} to {new_offset}")
                self._patched_moov[offset_pos:offset_pos+4] = new_offset.to_bytes(displacement, byteorder='big')
    
    def _classify_atom(self, atom: Atom):
        # atom.container = self
        # atom.load_contents(self.fp)
        if atom.name == 'ftyp':
            self.ftyp = atom
        elif atom.name == 'moov':
            atom.load_children()
            self.moov = atom
        elif atom.name == 'free':
            self.free = atom
        elif atom.name == 'mdat':
            self.mdat = atom
        elif not hasattr(self, atom.name):
            setattr(self, atom.name, atom)
        return atom
    
    def _get_chunks(self, limit: int, stream = None, chunksize:int = None):
        if stream is None:
            stream = self.fp
        chunk_size = chunksize or mmap.PAGESIZE
        while chunk_size < (2 ** 15):
            chunk_size *= 2
        remaining = limit
        while remaining:
            chunk = stream.read(min(remaining, chunk_size))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk

    @property
    def boundaries(self):
        return list(map(lambda a: a.named_boundaries, self.atoms))

    @property 
    def faststart(self):
        if not self._is_relocatable():
            return self.atoms
        temp_ordinal = self.mdat.ordinal
        self.mdat.ordinal = self.moov.ordinal
        self.moov.ordinal = temp_ordinal
        self.moov.setcontents(self.patched_moov)
        self.atoms.sort(key=lambda atom: atom.ordinal)
        for index, atm in enumerate(self.atoms):
            atm.contents.seek(0)
            if index == 0:
                continue
            atm.offset = self.atoms[index-1].offset + self.atoms[index-1].size
        return self.atoms

    @property
    @dual_mode
    def faststart_boundaries(self):
        return list(map(lambda a: a.named_boundaries, self.faststart))

    @property
    def patched_moov(self):
        if not self._patched_moov:
            self._patch_moov()
        return self._patched_moov
    
    def _get_moov_atom(self):
        """
        Deprecated. 'moov' is now an Mp4 attribute.
        """
        for atom in self.atoms:
            if atom.name == 'moov':
                return atom
        return None
    
    def _is_compressed(self):
        for atom in self.moov.children:
            if atom.name == 'cmov':
                print(f"Warning!\nFile {self.filename} cannot be optimized for streaming because it's compressed.")
                return True
        return False
    
    def stream(self, begin: int=0, end: int=None):
        for atm in self.faststart:
            atm.contents.seek(0)
            if atm.name not in ['mdat', 'moov']:
                yield atm.contents.read()
            else:
                chunkgen = self._get_chunks(limit=atm.size, stream=atm.contents)
                for chunk in chunkgen:
                    try:
                        yield chunk
                    except:
                        chunkgen.close()
                        break
            print(f"Mp4 '{atm.name}' stream sent succesfully ({atm.size:,} bytes).")

    @dual_mode
    def stream_range(self, begin: int=0, end: int=0):
        if not end:
            end = self.filesize - 1
        beginner, ender = {} , {}
        for atom in self.faststart:
            if begin in range(*atom.boundaries):
                beginner['name'] = atom.name
                beginner['ordinal'] = atom.ordinal
                beginner['offset'] = begin - atom.offset
            if end in range(*atom.boundaries):
                ender['name'] = atom.name
                ender['ordinal'] = atom.ordinal
                ender['offset'] = end - atom.offset
        if not ender:
            atom = self.faststart[-1]
            ender['name'] = atom.name
            ender['ordinal'] = atom.ordinal
            ender['offset'] = atom.size - 1
        if not beginner:
            atom = self.faststart[0]
            ender['name'] = atom.name
            ender['ordinal'] = atom.ordinal
            ender['offset'] = 0
        fragment = None
        for atom in self.faststart:
            if atom.ordinal < beginner.get('ordinal'):
                continue
            if atom.ordinal > ender.get('ordinal'):
                return
            if atom.ordinal == beginner.get('ordinal'):
                frag_begin = beginner.get('offset')
                if atom.ordinal == ender.get('ordinal'):
                    length = ender.get('offset') - frag_begin + 1
                    # fragment = atom.contents[beginner.get('offset'):ender.get('offset')]
                else:
                    length = atom.size - frag_begin
                    # fragment = atom.contents[beginner.get('offset'):]
            elif atom.ordinal == ender.get('ordinal'):
                frag_begin = 0
                length = ender.get('offset') + 1
                # fragment = atom.contents[:ender.get('offset')]
            else:
                frag_begin = 0
                length = atom.size
                # fragment = atom.contents[:]
            atom.contents.seek(frag_begin)
            gen = self._get_chunks(length, atom.contents)
            for chunk in gen:
                yield chunk

    async def async_stream_range(self, begin: int=0, end: int=0):
        async def _get_chunks(limit: int, stream = None, chunksize:int = None):
            if stream is None:
                stream = self.fp
            chunk_size = chunksize or mmap.PAGESIZE
            while chunk_size < (2 ** 15):
                chunk_size *= 2
            remaining = limit
            while remaining:
                chunk = await asyncio.to_thread(stream.read, min(remaining, chunk_size))
                if not chunk:
                    return
                remaining -= len(chunk)
                yield chunk

        if not end:
            end = self.filesize - 1
        beginner, ender = {} , {}
        for atom in self.faststart:
            if begin in range(*atom.boundaries):
                beginner['name'] = atom.name
                beginner['ordinal'] = atom.ordinal
                beginner['offset'] = begin - atom.offset
            if end in range(*atom.boundaries):
                ender['name'] = atom.name
                ender['ordinal'] = atom.ordinal
                ender['offset'] = end - atom.offset
        if not ender:
            atom = self.faststart[-1]
            ender['name'] = atom.name
            ender['ordinal'] = atom.ordinal
            ender['offset'] = atom.size - 1
        if not beginner:
            atom = self.faststart[0]
            ender['name'] = atom.name
            ender['ordinal'] = atom.ordinal
            ender['offset'] = 0
        fragment = None
        for atom in self.faststart:
            if atom.ordinal < beginner.get('ordinal'):
                continue
            if atom.ordinal > ender.get('ordinal'):
                return
            if atom.ordinal == beginner.get('ordinal'):
                frag_begin = beginner.get('offset')
                if atom.ordinal == ender.get('ordinal'):
                    length = ender.get('offset') - frag_begin + 1
                    # fragment = atom.contents[beginner.get('offset'):ender.get('offset')]
                else:
                    length = atom.size - frag_begin
                    # fragment = atom.contents[beginner.get('offset'):]
            elif atom.ordinal == ender.get('ordinal'):
                frag_begin = 0
                length = ender.get('offset') + 1
                # fragment = atom.contents[:ender.get('offset')]
            else:
                frag_begin = 0
                length = atom.size
                # fragment = atom.contents[:]
            await asyncio.to_thread(atom.contents.seek, frag_begin)
            gen = _get_chunks(length, atom.contents)
            async for chunk in gen:
                yield chunk

    def save(self, outputfile: str = 'out.mp4'):
        with open(outputfile, 'wb') as fp:
            for chunk in self.stream():
                fp.write(chunk)

        print(f"Mp4 file {self.filename} saved succesfully to {outputfile}.")

    def quicklist(self):
        fileline = f"File: {self.filename}"
        sizeline= f"Size: {self.filesize:,}"
        underline = "_" * max(len(fileline), len(sizeline))
        return [underline, fileline, sizeline, underline, *list(map(repr, self.atoms))]
    
def main():
    parser = argparse.ArgumentParser(description='Command line arguments for Mp4Parser', prog='mp4parser')
    parser.add_argument('-V', '--version', action='version', version=f"{parser.prog} v {oxi_version}", help=f"Shows {parser.prog} version and exits.")
    parser.add_argument('inputfile', type=str, help="Name of the file to be listed/processed.")
    parser.add_argument('-o', '--outputfile', type=str, default='out.mp4', help="Name of the file you wish to save to. Defaults to 'out.mp4'")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-s', '--save', action="store_true", help="Use this option to save the input file to a new one.")
    group.add_argument('-l', '--list', action="store_true", help="Shows a list of the main level atoms contained in the input file.")
    group.add_argument('-L', '--full-list', action="store_true", help="Shows a detailed list of the atoms contained in the input file.")
    
    args = parser.parse_args()
    filename = args.inputfile
    
    try:
        mp4 = Mp4(filename)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit

    if  args.save:
        mp4.save(args.outputfile)
    elif args.list:
        print('\n'.join(mp4.quicklist()))
    elif args.full_list:
        print(mp4)
    else:
        print('\n'.join(mp4.quicklist()))

if __name__ == '__main__':
    main()

