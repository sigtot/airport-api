from bottle import route, run, template, response, static_file, debug, redirect
import csv
import json
import os.path
from os import listdir
from os.path import isfile, join
import argparse
import glob
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Constants
LINE_RETURN_COUNT_MAX = 100 # How many records to return in a dump
CSVPATH_DEFAULT = './data/'
# CSVFILENAME_DEFAULT = 'IME-US-list.csv'
PORT_DEFAULT = 8983

# Globals
csvpath = './data/'
csvreader = None

csvfields = []
csvcontents = []
csvdict = {}

_filelist = []

# Fetch arguments
parser = argparse.ArgumentParser(description='Expose CSV via REST')
parser.add_argument('-d', '--datapath', type=str, nargs='?', default=CSVPATH_DEFAULT)
parser.add_argument('-f', '--filename', type=str, nargs='?', default=None)
parser.add_argument('-t', '--template', type=str, nargs='?', default=None)
parser.add_argument('-p', '--port', type=int, nargs='?', default=PORT_DEFAULT)
parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
parser.add_argument('-q', '--quiet', help='No output', action='store_true')
parser.add_argument('-z', '--dev-mode', help='Dev mode - debug mode & reloading', action='store_true')
parser.add_argument('-C', '--critmaj', help='Only include Critical and Major Severity defects', action='store_true')
args = parser.parse_args()

csvpath = args.datapath
csvfilename = args.filename
fname_glob = args.template
port = args.port
verbose = args.verbose
quiet = args.quiet
devmode = args.dev_mode
critmaj = args.critmaj

# Don't allow -q and -v
if verbose and quiet:
  logging.fatal("Cannot set both 'verbose' and 'quiet' parameters")
  exit(101)

# Routes
@route('/')
def home():
  return 'home page'

@route('/_admin')
def admin():
  return '<h1>admin page</h1><h2>Filename</h2>' + csvfilename + '<h2># of records</h2>' + str(len(_filelist) - 1) + "<h2>First file</h2><p>" + getFirstFilename() + " - <a href='/_admin/redirect/" + getFirstFilename() + "'>select</a></p><h2>Last file</h2>" + getLastFilename() + " - <a href='/_admin/redirect/" + getLastFilename() + "'>select</a></p><h2>Template</h2><p>" + (fname_glob if fname_glob else "<em>none set</em>") + "</p><h2>Fields</h2><UL><LI>" + '</LI><LI>'.join(csvfields) + "</LI></UL>\n" + "<h2>Available data files</h2>" + listDataFiles()

@route('/_admin/show/fields')
def adminShowfields():
  return "<UL><LI>" + '</LI><LI>'.join(csvcontents[0]) + "</LI></UL>"

@route('/_admin/get/fields')
def adminGetFields():
  response.add_header('Content-type', 'application/json')
  return json.dumps(csvcontents[0])

@route('/_admin/get/filenames')
def adminGetFilenames():
  global filelist
  filelist = getDataFiles()
  return buildResponseObjectSuccess(filelist)

@route('/_admin/get/selectedFile')
def adminGetSelectedFile():
  global csvfilename
  return buildResponseObjectSuccess(csvfilename)

@route('/_admin/get/template')
def adminGetTemplate():
  global fname_glob
  return fname_glob

@route('/_admin/set/template/<new_template>')
def adminSetTemplate(new_template):
  global fname_glob
  fname_glob = new_template
  getDataFiles()
  redirect('/_admin')

@route('/_admin/redirect/<new_filename>')
def adminRedirect(new_filename):
  if (os.path.isfile(os.sep.join([csvpath, new_filename]))):
    logging.info("adminRedirect: reading in new file: " + new_filename)
    read_file(new_filename)
    return buildResponseObjectSuccessOk()
  else:
    return buildResponseObjectError(["File not found"])

@route('/_admin/redirect-latest')
def adminRedirectLatest():
  read_file(getLastFilename())
  return buildResponseObjectSuccessOk()

@route('/_admin/redirect-first')
def adminRedirectFirst():
  read_file(getFirstFilename())
  return buildResponseObjectSuccessOk()

@route('/get/<id_value>')
def getIdValue(id_value):
  result = {}
  row = csvdict[id_value]
  fieldCtr = 0
  for f in row:
    result[csvfields[fieldCtr]] = f
    fieldCtr += 1
  return buildResponseObjectSuccess(result)

@route('/get/<field>/<value>')
def getFieldValue(field, value):
  result_rows = []
  # Get the # of the field you're searching for
  fieldnum = csvfields.index(field)
  for r in csvcontents:
    if r[fieldnum] == value: # Match, so save the row
      hit = {}
      fieldCtr = 0
      # Add field names
      for f in r:
        hit[csvfields[fieldCtr]] = f
        fieldCtr += 1
      result_rows.append(hit)
  return buildResponseObjectSuccess(result_rows)

@route('/get/<field1>/<value1>/<field2>/<value2>')
def getFieldValueDouble(field1, value1, field2, value2):
  # Handle empty field spec
  if value2 == '""':
    value2 = ""
  result_rows = []
  # Get the # of the field you're searching for
  fieldnum1 = csvfields.index(field1)
  fieldnum2 = csvfields.index(field2)
  for r in csvcontents:
    if (r[fieldnum1] == value1) and (r[fieldnum2] == value2): # Match, so save the row
      hit = {}
      fieldCtr = 0
      # Add field names
      for f in r:
        if (fieldCtr < len(csvfields)):
          hit[csvfields[fieldCtr]] = f
        fieldCtr += 1
      result_rows.append(hit)
  return buildResponseObjectSuccess(result_rows)

@route('/get/<field1>/<value1>/<field2>/<value2>/<field3>/<value3>')
def getFieldValueTriple(field1, value1, field2, value2, field3, value3):
  result_rows = []
  # Get the # of the field you're searching for
  fieldnum1 = csvfields.index(field1)
  fieldnum2 = csvfields.index(field2)
  fieldnum3 = csvfields.index(field3)
  for r in csvcontents:
    if (r[fieldnum1] == value1) and (r[fieldnum2] == value2) and (r[fieldnum3] == value3): # Match, so save the row
      hit = {}
      fieldCtr = 0
      # Add field names
      for f in r:
        hit[csvfields[fieldCtr]] = f
        fieldCtr += 1
      result_rows.append(hit)
  return buildResponseObjectSuccess(result_rows)

@route('/count/<field>/<value>')
def countFieldValue(field, value):
  # Get the # of the field you're searching for
  fieldnum = csvfields.index(field)
  counter = 0
  for r in csvcontents:
    if r[fieldnum] == value: # Match, so increment the counter
      counter += 1
  return buildResponseObjectSuccessCount(counter)

@route('/count/<field1>/<value1>/<field2>/<value2>')
def countFieldValueTwo(field1, value1, field2, value2):
  # Get the # of the field you're searching for
  fieldnum1 = csvfields.index(field1)
  fieldnum2 = csvfields.index(field2)
  counter = 0
  for r in csvcontents:
    if (r[fieldnum1] == value1) and (r[fieldnum2] == value2): # Match, so increment the counter
      counter += 1
  return buildResponseObjectSuccessCount(counter)

@route('/count/<field1>/<value1>/<field2>/<value2>/<field3>/<value3>')
def countFieldValueThree(field1, value1, field2, value2, field3, value3):
  # Get the # of the field you're searching for
  fieldnum1 = csvfields.index(field1)
  fieldnum2 = csvfields.index(field2)
  fieldnum3 = csvfields.index(field3)
  counter = 0
  for r in csvcontents:
    if (r[fieldnum1] == value1) and (r[fieldnum2] == value2) and (r[fieldnum3] == value3): # Match, so increment the counter
      counter += 1
  return buildResponseObjectSuccessCount(counter)

@route('/list/<field>')
def listValuesByField(field):
  values = {}
  fieldnum = csvfields.index(field)
  for r in csvcontents:
    if not r[fieldnum] in values:
      values[r[fieldnum]] = 1
    else:
      values[r[fieldnum]] += 1
  return buildResponseObjectSuccess(values)

@route('/list/<field>/<filter>/<value>')
def listValuesByFieldFiltered(field, filter, value):
  values = {}
  fieldnum = csvfields.index(field)
  filternum = csvfields.index(filter)
  for r in csvcontents:
    if (r[filternum] == value):
      if not r[fieldnum] in values:
        values[r[fieldnum]] = 1
      else:
        values[r[fieldnum]] += 1
  return buildResponseObjectSuccess(values)

def read_file(fname):
  global csvfields, csvfilename, csvcontents, csvdict
  csvfields = []
  csvfilename = fname
  csvcontents = []
  csvdict = {}
  with open(os.sep.join([csvpath, csvfilename]), 'r', encoding='utf-8', errors='replace') as csvfile:
    csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
    csvfields = next(csvreader) # Read in the field names
    # logging.debug("csvfields: %s" % (csvfields))
    if (critmaj): # Only capture the severityPos if critmaj is set
      severityPos = csvfields.index("Severity") # Store the severity position for later
    else:
      severityPos = None
    for row in csvreader:
      if (critmaj and (row[severityPos] == "Minor Problem" or row[severityPos] == "Cosmetic")):
        # logging.debug("Skipping Minor/Cosmetic problem")
        pass
      else:
        csvcontents.append(row)
        csvdict[row[0]] = row
      # logging.debug("...setting csvdict[" + str(row[0]) + "]")
    # csvfields = csvcontents[0]
  # logging.debug("...csvfields len = " + str(len(csvfields)))

def buildBasicResponseObject(status, remainder = {}):
  response = {}
  response['meta'] = {}
  response['meta']['status'] = status
  response['meta']['path'] = csvpath
  response['meta']['filename'] = csvfilename
  response['meta'].update(remainder)
  return(response)

def buildResponseObjectSuccessCount(counter):
  result = buildBasicResponseObject('success')
  result['data'] = { 'count': counter }
  return result

def buildResponseObjectSuccessOk():
  result = buildBasicResponseObject('success')
  return result

def buildResponseObjectSuccess(data):
  result = buildBasicResponseObject('success', { 'hit_count': len(data) })
  result['data'] = data
  return result

def buildResponseObjectError(errors):
  result = buildBasicResponseObject('error', { 'error_count': len(errors) })
  result['errors'] = errors
  return result

def getDataFiles():
  global csvpath, _filelist, fname_glob
  if (fname_glob):   # Glob/template specified
    logging.info("fname_glob set (%s)..." % (csvpath + os.path.sep + fname_glob))
    onlyfiles = [os.path.basename(f) for f in glob.glob(csvpath + os.path.sep + fname_glob)]
  else:              # No globbing/template
    logging.info("fname_glob not set...")
    onlyfiles = [f for f in listdir(csvpath) if (isfile(join(csvpath, f)) and f.endswith(".csv"))]
  _filelist = sorted(onlyfiles, reverse=True)
  return(_filelist)

def getLastFilename():
  return(getDataFiles()[0])

def getFirstFilename():
  return(getDataFiles()[-1])

def listDataFiles():
  result = "<UL>"
  filelist = getDataFiles()
  for f in filelist:
    result += "<LI><A HREF='/_admin/redirect/" + f + "'>" + f + "</A></LI>"
  result += "</UL>"
  return result

if __name__ == "__main__":
  # Verify that the path exists
  if (not os.path.exists(csvpath)):
    logging.fatal("Path (%s) was not found... " % (csvpath))
    exit(101)
  else:
    _filelist = getDataFiles()
    if None == csvfilename:
      csvfilename = _filelist[0]
    # Verify the file exists
    if (not os.path.exists(csvpath + os.path.sep + csvfilename)):
      logging.fatal("Can't find file (path: %s; name: %s). Exiting" % (csvpath, csvfilename))
      exit(102)
    else:
      logging.debug("Parsing %s" % (os.sep.join([csvpath, csvfilename])))

  if devmode:
    debug(True)
    # logging.basicConfig(level=logging.DEBUG)
    logging.debug("In Developer Mode... debug(True)", )

  if verbose or not quiet:
    logging.info("Data path: %s" % (csvpath))
    logging.info("Quiet? %s; Verbose? %s" % (quiet, verbose))
  read_file(csvfilename)

  if devmode:
    run(host='0.0.0.0', port=port, reloader=True)
  else:
    run(host='0.0.0.0', port=port)
