#!/usr/bin/env python
"""Discover_Tables.py

Inspects the currently open windows and finds those of interest to us--that is
poker table windows from supported sites.  Returns a list
of Table_Window objects representing the windows found.
"""
#    Copyright 2008, Ray E. Barker

#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#    
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#    
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

########################################################################

#    Standard Library modules
import os
import sys
import re

#    Win32 modules

if os.name == 'nt':
    import win32gui
    import win32process
    import win32api
    import win32con

#    FreePokerTools modules
import Configuration

#    Each TableWindow object must have the following attributes correctly populated:
#    tw.name = the table name from the title bar, which must to match the table name
#              from the corresponding hand history.
#    tw.site = the site name, e.g. PokerStars, FullTilt.  This must match the site
#            name specified in the config file.
#    tw.number = This is the system id number for the client table window in the 
#                format that the system presents it.  This is Xid in Xwindows and
#                hwnd in Microsoft Windows.
#    tw.title = The full title from the window title bar.
#    tw.width, tw.height = The width and height of the window in pixels.  This is 
#            the internal width and height, not including the title bar and 
#            window borders.
#    tw.x, tw.y = The x, y (horizontal, vertical) location of the window relative 
#            to the top left of the display screen.  This also does not include the
#            title bar and window borders.  To put it another way, this is the 
#            screen location of (0, 0) in the working window.

class Table_Window:
    def __init__(self, info = {}):
        if 'number' in info:    self.number = info['number']
        if 'exe' in info:       self.exe    = info['exe']
        if 'width' in info:     self.width  = info['width']
        if 'height' in info:    self.height = info['height']
        if 'x' in info:         self.x      = info['x']
        if 'y' in info:         self.y      = info['y']
        if 'site' in info:      self.site   = info['site']
        if 'title' in info:     self.title  = info['title']
        if 'name' in info:      self.name   = info['name']

    def __str__(self):
#    __str__ method for testing
        temp = 'TableWindow object\n'
        temp = temp + "    name = %s\n    site = %s\n    number = %s\n    title = %s\n" % (self.name, self.site, self.number, self.title)
#        temp = temp + "    game = %s\n    structure = %s\n    max = %s\n" % (self.game, self.structure, self.max)
        temp = temp + "    width = %d\n    height = %d\n    x = %d\n    y = %d\n" % (self.width, self.height, self.x, self.y)
        if getattr(self, 'tournament', 0):
            temp = temp + "    tournament = %d\n    table = %d" % (self.tournament, self.table)
        return temp

############################################################################
#    Top-level discovery routines--these are the modules interface
def discover(c):
    """Dispatch routine for finding all potential poker client windows."""
    if os.name == 'posix':
        tables = discover_posix(c)
    elif os.name == 'nt':
        tables = discover_nt(c)
    elif os.name == 'mac':
        tables = discover_mac(c)
    else:
        tables = {}
    return tables

def discover_table_by_name(c, tablename):
    """Dispatch routine for finding poker client windows with the given name."""
    if os.name == 'posix':
        info = discover_posix_by_name(c, tablename)
    elif os.name == 'nt':
        info = discover_nt_by_name(c, tablename)
    elif os.name == 'mac':
        info = discover_mac_by_name(c, tablename)
    else:
        return None
    if info == None:
        return None
    return Table_Window(info)

def discover_tournament_table(c, tour_number, tab_number):
    """Dispatch routine for finding poker clients with tour and table number."""
    if os.name == 'posix':
        info = discover_posix_tournament(c, tour_number, tab_number)
    elif os.name == 'nt':
        info = discover_nt_tournament(c, tour_number, tab_number)
    elif os.name == 'mac':
        info = discover_mac_tournament(c, tour_number, tab_number)
    else:
        return None
    if info:
        return Table_Window(info)
    return None

#############################################################################
# Posix (= XWindows) specific routines
def discover_posix(c):
    """Poker client table window finder for posix/Linux = XWindows."""
    tables = {}
    for listing in os.popen('xwininfo -root -tree').readlines():
#    xwininfo -root -tree -id 0xnnnnn    gets the info on a single window
        for s in c.get_supported_sites():
            params = c.get_site_parameters(s)
            if re.search(params['table_finder'], listing):
                if re.search('Lobby', listing):                continue
                if re.search('Instant Hand History', listing): continue
                if re.search('\"Full Tilt Poker\"', listing):  continue # FTP Lobby
                if re.search('History for table:', listing):   continue
                if re.search('has no name', listing):          continue
                info = decode_xwininfo(c, listing)
                if info['site'] == None:                       continue
                if info['title'] == info['exe']:               continue
#    this appears to be a poker client, so make a table object for it
                tw = Table_Window(info)
                eval("%s(tw)" % params['decoder'])
                tables[tw.name] = tw
    return tables

def discover_posix_by_name(c, tablename):
    """Find an XWindows poker client of the given name."""
    for listing in os.popen('xwininfo -root -tree').readlines():
        if re.search(tablename, listing):
            if re.search('History for table:', listing): continue
            info = decode_xwininfo(c, listing)
            if not info['name'] == tablename:            continue
            return info
    return None

def discover_posix_tournament(c, t_number, s_number):
    """Finds the X window for a client, given tournament and table nos."""
    search_string = "%s.+Table\s%s" % (t_number, s_number)
    for listing in os.popen('xwininfo -root -tree').readlines():
        if re.search(search_string, listing):
            return decode_xwininfo(c, listing)
    return None

def decode_xwininfo(c, info_string):
    """Gets window parameters from xwinifo string--XWindows."""
    info = {}
    mo = re.match('\s+([\dxabcdef]+) (.+):\s\(\"([a-zA-Z.]+)\".+  (\d+)x(\d+)\+\d+\+\d+  \+(\d+)\+(\d+)', info_string)
    if not mo:
        return None
    else:
        info['number'] = int( mo.group(1), 0)
        info['exe']    = mo.group(3)
        info['width']  = int( mo.group(4) )
        info['height'] = int( mo.group(5) )
        info['x']      = int( mo.group(6) )
        info['y']      = int( mo.group(7) )
        info['site']   = get_site_from_exe(c, info['exe'])
        info['title']  = re.sub('\"', '', mo.group(2))
        title_bits     = re.split(' - ', info['title'])
        info['name']   = clean_title(title_bits[0])
    return info

##############################################################################
#    NT (= Windows) specific routines
def discover_nt(c):
    """    Poker client table window finder for Windows."""
#
#    I cannot figure out how to get the inside dimensions of the poker table
#    windows.  So I just assume all borders are 3 thick and all title bars
#    are 29 high.  No doubt this will be off when used with certain themes.
#
    b_width = 3
    tb_height = 29
    titles = {}
    tables = {}
    win32gui.EnumWindows(win_enum_handler, titles)
    for hwnd in titles.keys():
        if re.search('Logged In as', titles[hwnd], re.IGNORECASE) and not re.search('Lobby', titles[hwnd]):
            if re.search('Full Tilt Poker', titles[hwnd]):
                continue
            tw = Table_Window()
            tw.number = hwnd
            (x, y, width, height) = win32gui.GetWindowRect(hwnd)
            tw.title  = titles[hwnd]
            tw.width  = int( width ) - 2*b_width
            tw.height = int( height ) - b_width - tb_height
            tw.x      = int( x ) + b_width
            tw.y      = int( y ) + tb_height
            if re.search('Logged In as', titles[hwnd]):
                tw.site = "PokerStars"
            elif re.search('Logged In As', titles[hwnd]): #wait, what??!
                tw.site = "Full Tilt"
            else:
                tw.site = "Unknown"
                sys.stderr.write("Found unknown table = %s" % tw.title)
            if not tw.site == "Unknown":
                eval("%s(tw)" % c.supported_sites[tw.site].decoder)
            else:
                tw.name = "Unknown"
            tables[len(tables)] = tw
    return tables

def discover_nt_by_name(c, tablename):
    """Finds poker client window with the given table name."""
    titles = {}
    win32gui.EnumWindows(win_enum_handler, titles)
    for hwnd in titles:
        if titles[hwnd].find(tablename) == -1: continue
        if titles[hwnd].find("History for table:") > -1: continue
        if titles[hwnd].find("HUD:") > -1: continue
        if titles[hwnd].find("Chat:") > -1: continue
        return decode_windows(c, titles[hwnd], hwnd)
    return None

def discover_nt_tournament(c, tour_number, tab_number):
    """Finds the Windows window handle for the given tournament/table."""
    search_string = "%s.+%s" % (tour_number, tab_number)

    titles ={}
    win32gui.EnumWindows(win_enum_handler, titles)
    for hwnd in titles:
        if re.search(search_string, titles[hwnd]):
            return decode_windows(c, titles[hwnd], hwnd)
    return None

def get_nt_exe(hwnd):
    """Finds the name of the executable that the given window handle belongs to."""
    processid = win32process.GetWindowThreadProcessId(hwnd)
    pshandle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, processid[1])
    exename = win32process.GetModuleFileNameEx(pshandle, 0)
    win32api.CloseHandle(pshandle)
    return exename

def decode_windows(c, title, hwnd):
    """Gets window parameters from the window title and handle--Windows."""

#    I cannot figure out how to get the inside dimensions of the poker table
#    windows.  So I just assume all borders are 3 thick and all title bars
#    are 29 high.  No doubt this will be off when used with certain themes.
    b_width = 3
    tb_height = 29

    info = {}
    info['number'] = hwnd
    info['title'] = re.sub('\"', '', title)
    (x, y, width, height) = win32gui.GetWindowRect(hwnd)

    info['x']      = int(x)  + b_width
    info['y']      = int( y ) + tb_height
    info['width']  = int( width ) - 2*b_width
    info['height'] = int( height ) - b_width - tb_height
    info['exe']    = get_nt_exe(hwnd)

    title_bits = re.split(' - ', info['title'])
    info['name'] = title_bits[0]
    info['site']   = get_site_from_exe(c, info['exe'])

    return info

def win_enum_handler(hwnd, titles):
    titles[hwnd] = win32gui.GetWindowText(hwnd)
  
###################################################################
#    Utility routines used by all the discoverers.
def get_site_from_exe(c, exe):
    """Look up the site from config, given the exe."""
    for s in c.get_supported_sites():
        params = c.get_site_parameters(s)
        if re.search(params['table_finder'], exe):
            return params['site_name']
    return None

def pokerstars_decode_table(tw):
#    Extract poker information from the window title.  This is not needed for
#    fpdb, since all that information is available in the db via new_hand_number.
#    This is needed only when using the HUD with a backend less integrated.
    title_bits = re.split(' - ', tw.title)
    name = title_bits[0]
    mo = re.search('Tournament (\d+) Table (\d+)', name)
    if mo:
        tw.tournament = int( mo.group(1) )
        tw.table      = int( mo.group(2) )
        tw.name       = name
    else:
        tw.tournament = None
        tw.name = clean_title(name)
    mo = re.search('(Razz|Stud H/L|Stud|Omaha H/L|Omaha|Hold\'em|5-Card Draw|Triple Draw 2-7 Lowball|Badugi)', tw.title)
    
    tw.game = mo.group(1).lower()
    tw.game = re.sub('\'', '', tw.game)
    tw.game = re.sub('h/l', 'hi/lo', tw.game)
    
    mo = re.search('(No Limit|Pot Limit)', tw.title)
    if mo:
        tw.structure = mo.group(1).lower()
    else:
        tw.structure = 'limit'
        
    tw.max = None
    if tw.game in ('razz', 'stud', 'stud hi/lo'):
        tw.max = 8
    elif tw.game in ('5-card draw', 'triple draw 2-7 lowball'):
        tw.max = 6
    elif tw.game == 'holdem':
        pass
    elif tw.game in ('omaha', 'omaha hi/lo'):
        pass

def fulltilt_decode_table(tw):
#    Extract poker information from the window title.  This is not needed for
#    fpdb, since all that information is available in the db via new_hand_number.
#    This is needed only when using the HUD with a backend less integrated.
    title_bits = re.split(' - ', tw.title)
    name = title_bits[0]
    tw.tournament = None
    tw.name = clean_title(name)

def clean_title(name):
    """Clean the little info strings from the table name."""
#    these strings could go in a config file
    for pattern in [' \(6 max\)', ' \(heads up\)', ' \(deep\)',
                ' \(deep hu\)', ' \(deep 6\)', ' \(2\)',
                ' \(edu\)', ' \(edu, 6 max\)', ' \(6\)',
                ' \(speed\)', 
                ' no all-in', ' fast', ',', ' 50BB min', '\s+$']:
        name = re.sub(pattern, '', name)
    name = name.rstrip()
    return name

###########################################################################
#    Mac specific routines....all stubs for now
def discover_mac_tournament(c, tour_number, tab_number):
    """Mac users need help."""
    return None

def discover_mac(c):
    """Poker client table window finder for Macintosh."""
    tables = {}
    return tables

def discover_mac_by_name(c, tablename):
    """Oh, the humanity."""
    # again, i have no mac to test this on, sorry -eric
    return None

###########################################################################
#   Main function used for testing
if __name__=="__main__":
    c = Configuration.Config()

    print discover_table_by_name(c, "Ringe")
#    print discover_tournament_table(c, "118942908", "3")

#    tables = discover(c)
#    for t in tables.keys():
#        print tables[t]

    print "press enter to continue"
    sys.stdin.readline()
