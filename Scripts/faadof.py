# -*- coding: utf-8 -*-
'''
Created on Apr 23, 2012
@param The path of the output geodatabase.
@param The path to the input digital obstacle file (DOF) 

@author: JacobsJ
@todo: add optional command line parameter for which z value to use in geometry: above ground or above sea level column
'''

import sys, os.path, re, datetime, urllib2, remotezip
print "Importing arcpy..."
import arcpy
print "Finished importing arcpy..."

_jdatere = re.compile("(?P<year>\d{4})(?P<days>\d{3})")
_wgs84 = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433],AUTHORITY["EPSG",4326]]'
_ngvd1929 = 'VERTCS["NGVD_1929",VDATUM["National_Geodetic_Vertical_Datum_1929"],PARAMETER["Vertical_Shift",0.0],PARAMETER["Direction",1.0],UNIT["Foot_US",0.3048006096012192],AUTHORITY["EPSG",5702]]'
_navd1988 = 'VERTCS["NAVD_1988",VDATUM["North_American_Vertical_Datum_1988"],PARAMETER["Vertical_Shift",0.0],PARAMETER["Direction",1.0],UNIT["Meter",1.0],AUTHORITY["EPSG",5703]]'

_zDate = datetime.date(2001, 3, 12) # Records on or after this date are in NAVD 1988.  Prior are NGVD 1929.

def _parseCurrencyDate(line, out_format=None):
	"""Parses the currency date
	"""
	regex = re.compile(r"\s*CURRENCY\sDATE\s*=\s*(?P<month>\d{2})/(?P<day>\d{2})/(?P<year>\d{2})",re.IGNORECASE)
	r = regex.search(line)
	output = None
	if r is not None:
		d = r.groupdict()
		if out_format == "str":
			output = "%(month)s-%(day)s-20%(year)s" % d
		else:
			output = datetime.date(int("20" + d["year"]), int(d["month"]), int(d["day"]))
	return output
		

def julianDateToDate(jDate):
	match =_jdatere.match(jDate)
	if match:
		d = match.groupdict()
		year = int(d["year"])
		days = int(d["days"])
		date = datetime.date(year,1,1) + datetime.timedelta(days=days-1)
		return date
	
def dmsToDD(degrees, minutes, seconds, hemisphere):
	if hemisphere == "S" or hemisphere == "W":
		dd = degrees * - 1 - float(minutes) / 60 - float(seconds)/3600
	else:
		dd = degrees + float(minutes) / 60 + float(seconds)/3600
	return dd

class Dms(object): 
	def __init__(self, degrees, minutes, seconds, hemisphere):
		self.degrees = degrees
		self.minutes = minutes
		self.seconds = seconds
		self.hemisphere = hemisphere
	def toDD(self):
		dd = dmsToDD(self.degrees, self.minutes, self.seconds, self.hemisphere)
		return dd
	def __str__(self, *args, **kwargs):
		# return "%s %s %s %s" % (self.degrees, self.minutes, self.seconds, self.hemisphere)
		if re.match("[SW]", self.hemisphere):
			return "%s %s %s %s" % (self.degrees, self.minutes, self.seconds, self.hemisphere)
		else:
			return "%s %s %s %s" % (self.degrees, self.minutes, self.seconds, self.hemisphere)


class Obstacle(object):
	def __init__(self, line):
		self.orsCode = line[0:2]
		self.obstacleNumber = line[3:10]
		self.verificationStatus = line[10]
		self.countryId = line[12:15].rstrip()
		self.stateId = line[15:18].rstrip()
		self.cityName = line[18:34].rstrip()
		
		self.latitude = Dms(int(line[35:37]), int(line[38:40]), float(line[41:46]), line[46])
		self.longitude = Dms(int(line[48:51]), int(line[52:54]), float(line[55:60]), line[60])
		
		self.obstacleType = line[62:74].rstrip()
		self.quantity = int(line[75])
		self.aglHT = int(line[77:82])
		self.AmslHT = int(line[83:88])
		
		self.lighting = line[89]
		self.horizontalAccuracy = line[91].rstrip()
		self.verticalAccuracy = line[93].rstrip()
		self.markIndicator = line[95]
		
		self.faaStudyNo = line[97:111].rstrip()
		self.action = line[112]
		self.date = julianDateToDate(line[114:121])
	def __str__(self, *args, **kwargs):
		return object.__str__(self, *args, **kwargs)

def addObstacleToRow(row, obstacle):
	row.orsCode = obstacle.orsCode
	row.obstacleNo = obstacle.obstacleNumber
	row.verificationStatus = obstacle.verificationStatus
	row.countryId = obstacle.countryId
	row.stateId = obstacle.stateId
	row.cityName = obstacle.cityName
	#	row.latitude = obstacle.latitude
	#	row.longitude = obstacle.longitude
	row.obstacleType = obstacle.obstacleType
	row.quantity = obstacle.quantity
	row.aglHT = obstacle.aglHT
	row.AmslHT = obstacle.AmslHT
	row.lighting = obstacle.lighting
	row.horizontalAccuracy = obstacle.horizontalAccuracy
	row.verticalAccuracy = obstacle.verticalAccuracy
	row.markIndicator = obstacle.markIndicator
	row.faaStudyNo = obstacle.faaStudyNo
	row.action = obstacle.action
	row.date = str(obstacle.date) # Dates have to be set as strings
	
	point = arcpy.Point()
	point.X = obstacle.longitude.toDD()
	point.Y = obstacle.latitude.toDD()
	point.Z = obstacle.aglHT
	pointGeometry = arcpy.PointGeometry(point)
	row.shape = pointGeometry



def createDomains(gdbPath):
	"""Creates file geodatabase domains for FAA Digital Obstacle Files.
	@param gdbPath: Path to a geodatabase.
	@author: Jeff Jacobson
	@organization: WSDOT
	"""
	domains = {}
	domains["OrsCode"] = {
	  "description": "ORS Code",
	  "domains" : {
		"01": "Alabama",
		"02": "Alaska",
		"04": "Arizona",
		"05": "Arkansas",
		"06": "California",
		"08": "Colorado",
		"09": "Connecticut",
		"10": "Delaware",
		"11": "DC",
		"12": "Florida",
		"13": "Georgia",
		"15": "Hawaii",
		"16": "Idaho",
		"17": "Illinois",
		"18": "Indiana",
		"19": "Iowa",
		"20": "Kansas",
		"21": "Kentucky",
		"22": "Louisiana",
		"23": "Maine",
		"24": "Maryland",
		"25": "Massachusetts",
		"26": "Michigan",
		"27": "Minnesota",
		"28": "Mississippi",
		"29": "Missouri",
		"30": "Montana",
		"31": "Nebraska",
		"32": "Nevada",
		"33": "New Hampshire",
		"34": "New Jersey",
		"35": "New Mexico",
		"36": "New York",
		"37": "North Carolina",
		"38": "North Dakota",
		"39": "Ohio",
		"40": "Oklahoma",
		"41": "Oregon",
		"42": "Pennsylvania",
		"44": "Rhode Island",
		"45": "South Carolina",
		"46": "South Dakota",
		"47": "Tennessee",
		"48": "Texas",
		"49": "Utah",
		"50": "Vermont",
		"51": "Virginia",
		"53": "Washington",
		"54": "West Virginia",
		"55": "Wisconsin",
		"56": "Wyoming",
		"CA": "Canada",
		"MX": "Mexico",
		"PR": "Puerto Rico",
		"BS": "Bahamas",
		"AG": "Antigua and Barbuda",
		"AI": "Anguilla",
		"AN": "Netherlands Antilles",
		"AW": "Aruba",
		"CU": "Cuba",
		"DO": "Dominican Republic",
		"GP": "Guadeloupe",
		"HN": "Honduras",
		"HT": "Haiti",
		"JM": "Jamaica",
		"KN": "St. Kitts and Nevis",
		"KY": "Cayman Islands",
		"MS": "Montserrat",
		"TC": "Turks and Caicos Islands",
		"VG": "British Virgin Islands",
		"VI": "Virgin Islands",
		"AS": "American Samoa",
		"FM": "Federated States of Micronesia",
		"GU": "Guam",
		"KI": "Kiribati",
		"MH": "Marshall Islands",
		"MI": "Midway Islands",
		"MP": "Northern Mariana Islands",
		"PW": "Palau",
		"RU": "Russia",
		"TK": "Tokelau",
		"WQ": "Wake Island",
		"WS": "Samoa",
		}
	}
	
	# Verification Status
	domains["VerificationStatus"] = {
		"description": "Verification Status",
		"domains": {
			"O": "verified",
			"U": "unverified"
		}
	}
	
	domains["LightingType"] = {
		"description": "Lighting Type",
		"domains": {
			"R":  "Red",
			"D":  "Medium intensity White Strobe & Red", 
			"H":  "High Intensity White Strobe & Red", 
			"M": "Medium Intensity White Strobe", 
			"S" :  "High Intensity White Strobe", 
			"F" :  'Flood', 
			"C" : "Dual Medium Catenary", 
			"W": "Synchronized Red Lighting", 
			"L" : "Lighted (Type Unknown)", 
			"N":  "None", 
			"U":  "Unknown"
		}
	}
	
	domains["HorizontalAccuracy"] = {
		"description": "Horizontal Accuracy",
		"domains": {
			"1": "+-20'",
			"2": "+-50'",
			"3": "+-100'",
			"4": "+-250'",
			"5": "+-500'",
			"6": "+-1000'",
			"7": "+-1/2 NM",
			"8": "+-1 NM",
			"9": "Unknown"
		}
	 }
	
	domains["VerticalAccuracy"] = {
		"description": "Vertical Accuracy",
		"domains": {
			"A": "+-3'",
			"B": "+-10'",
			"C": "+-20'",
			"D": "+-50'",
			"E": "+-125'",
			"F": "+-250'",
			"G": "+-500'",
			"H": "+-1000'",
			"I": "Unknown"
		}
	}
	
	
	domains["MarkIndicator"] = {
		"description": "Type of Marking",
		"domains": {
			"P":   "Orange or Orange and White Paint",
			"W": "White Paint Only",
			"M":  "Marked",
			"F":   "Flag Marker",
			"S":   "Spherical Marker",
			"N":  "None",
			"U":  "Unknown"
		}
	}
	
	domains["Action"] = {
		"description": "Action",
		"domains": {
			"A": "Add",
			"C": "Change",
			"D": "Dismantle"
		}
	}
	
	domains["StructureTypes"] = {
		"description": "Structure Types",
		"domains": {
			"AG EQUIP":"agricultural equipment",
			"ARCH":"arch",
			"BALLOON":"balloon: tethered; weather; other reconnaissance",
			"BLDG":"building",
			"BLDG-TWR":"latticework greater than 20' on building",
			"BRIDGE":"bridge",
			"CATENARY":"catenary: transmission line span/wire/cable",
			"COOL TWR":"nuclear cooling tower",
			"CRANE":"crane: permanent",
			"CRANE T":"crane: temporary",
			"CTRL TWR":"airport control tower",
			"DAM":"Dam",
			"DOME":"Dome",
			"ELECTRICAL SYSTEM":"Electrical System",
			"ELEVATOR":"silo; grain elevator",
			"FENCE":"Fence",
			"GENERAL UTILITY":"General Utility",
			"LIGHTHOUSE":"Lighthouse",
			"MONUMENT":"Monument",
			"NAVAID":"airport navigational aid",
			"PLANT":"plant: multiple close structures used for industrial purposes",
			"POLE":"flag pole; light pole",
			"REFINERY":"refinery: multiple close structures used for purifying crude materials",
			"RIG":"oil rig",
			"SIGN":"Sign",
			"SPIRE":"spire: steeple",
			"STACK":"stack: smoke; industrial",
			"STADIUM":"Stadium",
			"T-L TWR":"transmission line tower; telephone pole",
			"TANK":"tank: water; fuel",
			"TOWER":"Tower",
			"TRAMWAY":"Tramway",
			"TREE":"Tree",
			"VEGETATION":"Vegetation",
			"WINDMILL":"windmill: wind turbine"
		}
	}

	# Create table for domains
	arcpy.management.CreateTable("in_memory", "DomainValues")
	tempTable = "in_memory/DomainValues"
	arcpy.management.AddField(tempTable, "Name", "TEXT")
	arcpy.management.AddField(tempTable, "Value", "TEXT")
	
	for domainName in domains:
		cursor = arcpy.InsertCursor(tempTable)
		row = None
		domainDef = domains[domainName]
		domainValues = domainDef["domains"]
		for name in domainValues:
			row = cursor.newRow()
			row.Name = name
			row.Value = domainValues[name]
			cursor.insertRow(row)
		del row, cursor
	
		domainDescription = domainDef["description"]
		arcpy.management.TableToDomain(tempTable, "Name", "Value", gdbPath, domainName, domainDescription, "REPLACE")
		arcpy.management.DeleteRows(tempTable)
	arcpy.management.Delete(tempTable)

def createDofFeatureClass(out_path, name, projection):
	"""Creates the Digital Obstacle File feature class and defines its schema.
	@param out_path: The workspace (e.g., geodatabase) where the feature class will be created.
	@param name: The name that will be given to the feature class.
	@param projection: The projection that will be used by the feature class.
	"""
	arcpy.management.CreateFeatureclass(out_path, name, "POINT", None, None, "ENABLED", projection)
	fcPath = os.path.join(out_path, name)
	arcpy.management.AddField(fcPath, "OrsCode", "TEXT", None, None, 2, "ORS Code", "NON_NULLABLE", "REQUIRED", "OrsCode")
	arcpy.management.AddField(fcPath, "ObstacleNo", "TEXT", None, None, 7, "Obstacle Number", "NON_NULLABLE")
	arcpy.management.AddField(fcPath, "VerificationStatus", "TEXT", None, None, 1, "Verification Status", "NON_NULLABLE", "NON_REQUIRED", "VerificationStatus")
	arcpy.management.AddField(fcPath, "CountryId", "TEXT", None, None, 2, "Country Identifier")
	arcpy.management.AddField(fcPath, "StateId", "TEXT", None, None, 2, "State Identifier")
	arcpy.management.AddField(fcPath, "CityName", "TEXT", None, None, 16, "City Name")
	arcpy.management.AddField(fcPath, "ObstacleType", "TEXT", None, None, 12, "Obstacle Type", None, None, "StructureTypes")
	arcpy.management.AddField(fcPath, "Quantity", "SHORT")
	arcpy.management.AddField(fcPath, "AglHT", "SHORT", field_alias="Above Ground Level Height (Feet)")
	arcpy.management.AddField(fcPath, "AmslHt", "SHORT", field_alias="Above Mean Sea Level Height (Feet)")
	arcpy.management.AddField(fcPath, "Lighting", "TEXT", field_length=1, field_domain="LightingType")
	arcpy.management.AddField(fcPath, "HorizontalAccuracy", "TEXT", None, None, 1, "Horizontal Accuracy", None, None, "HorizontalAccuracy")
	arcpy.management.AddField(fcPath, "VerticalAccuracy", "TEXT", None, None, 1, "Vertical Accuracy", None, None, "VerticalAccuracy")
	arcpy.management.AddField(fcPath, "MarkIndicator", "TEXT", None, None, 1, "Mark Indicator", None, None, "Mark Indicator")
	arcpy.management.AddField(fcPath, "FaaStudyNo", "TEXT", None, None, 14, "FAA Study Number")
	arcpy.management.AddField(fcPath, "Action", "TEXT", None, None, 1, None, None, None, "Action")
	arcpy.management.AddField(fcPath, "Date", "DATE")

def createCurrencyDateTable(out_path, out_name="CurrencyDate", currencyDate=None):
	"""Creates the "CurrencyDate" table and optionally populates it.
	@param out_path: The path to the geodatabase where the table will be created.
	@type out_path: str
	@param out_name: The name to be given to the new table.
	@type out_name: str
	@param currencyDate: You can provide a currency date value to populate the CurrencyDate table.
	@type currencyDate: str or datetime.Date 
	"""
	# Join the gdb path and table name to get the full path to the table
	tablePath = os.path.join(out_path, out_name)
	# Create the table.
	arcpy.management.CreateTable(out_path, out_name)
	# Add the currency date field.
	arcpy.management.AddField(tablePath, "CurrencyDate", "DATE", field_alias="Currency Date")
	# If a currency date value has been provided, add a new row with the currency date.
	if currencyDate is not None:
		with arcpy.InsertCursor(tablePath) as cursor:
			row = cursor.newRow()
			# Date values are added to rows via cursor as strings.
			if type(currencyDate) == str:
				row.CurrencyDate = currencyDate
			elif type(currencyDate) == datetime.date:
				row.CurrencyDate = str(currencyDate)
			cursor.insertRow(row)
			del row
		pass

def createDofGdb(gdbPath):
	"""Creates a file Geodatabase for FAA DOF data.  Creates the necessary domains as well.
	@param gdbParam: The path where the GDB will be created.
	"""
	# Delete the GDB if it already exists.
	if arcpy.Exists(gdbPath):
		print "%s already exists.  Deleting..." % gdbPath
		arcpy.management.Delete(gdbPath)
	#Create a new GDB.
	print "Creating %s..." % gdbPath
	arcpy.management.CreateFileGDB(*os.path.split(gdbPath))
	print "Creating domains in %s..." % gdbPath
	createDomains(gdbPath)
	# Add feature class
	print "Creating feature class..." 
	createDofFeatureClass(gdbPath, "Obstacles", _wgs84 + ',' + _navd1988)


def downloadDofs(url="http://tod.faa.gov/tod/public/DOFS/", datafiles=('53-WA.Dat',), destDir="../Scratch"):
	"""Downloads the specified data files from the FAA website.
	@param url: The URL of the directory that contains the DOF data zip archives.
	@type url: str
	@param datafiles: A set of file names fo the .DAT files that are to be downloaded.
	@type dataFiles: set
	@param destDir: The destination directory where the data files will be copied to.
	@type destDir: str
	@return: Returns a list paths of the files that were written to the file system. 
	@rtype: list
	"""
	# This regular expression matches the links to the DOF_* zip files.  Captures are 2-digit year, month, and day, respectively.
	linkRe = re.compile(r"""<a href=['"](?P<path>/tod/public/DOFS/DOF_(\d{2})(\d{2})(\d{2})\.zip)['"]>""", re.IGNORECASE)
	
	print "Reading '%s'..." % url
	# Open the page and store the HTML in a variable.
	f = urllib2.urlopen(url)
	html = f.read()
	del f # Delete references to unused variables.
	
	# Extract all of the DOF URLs
	matches = linkRe.findall(html)
	# sample matches:
	#[
	#	('/tod/public/DOFS/DOF_111020.zip', '11', '10', '20'), 
	#	('/tod/public/DOFS/DOF_111215.zip', '11', '12', '15'), 
	#	('/tod/public/DOFS/DOF_120108.zip', '12', '01', '08'), 
	#	('/tod/public/DOFS/DOF_120304.zip', '12', '03', '04')
	#]
	# Convert the matches into a dictionary containing keys "url" and "date".
	data = map(lambda s: {
						"url": urllib2.urlparse.urljoin(url, s[0]), 
						"date": datetime.date(int("20" + s[1]), int(s[2]), int(s[3]))
						}, matches
			)
	
	# Loop through all of the paths and determine which is the newest.  Download that file.
	
	newest = None
	for info in data:
		if newest is None or newest["date"] < info["date"]:
			newest = info
	print data
	print "The newest file is %s." %  newest["url"]
	
	# Download the desired data files from the zip.
	hzfile = remotezip.HTTPZipFile(newest["url"])
	#hzfile.printdir()
	
	# Create the destination directory if it does not already exist.
	if not os.path.exists(destDir):
		os.mkdir(destDir)
	elif not os.path.isdir(destDir):
		raise "Destination directory path exists, but is not a directory."
	
	# Create the output list of table paths.
	destNames = []
	
	# Loop thorugh the list of requested data files.  Extract and save a copy of each.
	for fname in (datafiles):
		source_name = fname
		dest_fname = os.path.join(destDir, os.path.basename(fname))
		print "Extracing %s to %s" % (source_name, dest_fname)
		
		# Get the data for the requested file.
		f = hzfile.open(source_name)
		# Initialize the new file.
		new_file = None
		try:
			# Read the file data.
			data = f.read()
			# Create the destination file.
			new_file = open(dest_fname, 'wb') # must open file as binary (unless you know you're only dealing with text files).
			# Write the data from the source to destination.
			new_file.write(data)
			# Close the newly created file (the local copy).
			new_file.close()
			# Add this file's path to the output list of files.
			destNames.append(dest_fname)
		finally:
			# Close the http zip file.
			f.close()
			# Close the new file if it is open.
			if new_file is not None:
				new_file.close()
	
	return destNames

def readDofFile(dofPath):
	"""Reads DOF file and converts to Obstacle objects.
	@param dofPath: Path to the DOF file
	@param gdbPath: Path to the GDB.
	"""
	obstacles = []
	if os.path.exists(dofPath):
		with open(dofPath) as f:
			i = 0
			for line in f:
				if i == 0:
					pass # TODO: Do something with "Currency Date"
				elif i >= 4:
					obstacle = Obstacle(line)
					print "%s,%s" % (str(obstacle.longitude), str(obstacle.latitude))
					print "%s %s" % (obstacle.longitude.toDD(), obstacle.latitude.toDD())
					obstacles.append(obstacle)
				i += 1
				
	else:
		raise "File not found: %s" % dofPath
	return obstacles

def _readDofIntoGdb(dofPath, cursor88, cursor29):
	"""Reads a DOF file into a geodatabase using the specified cursors.
	@param dofPath: Path to the DOF file.
	@type dofPath: str
	@param cursor88: Cursor to the "Obstacles" feature class.
	@type cursor88: arcpy.InsertCursor
	@param cursor29: Cursor to the "Obstacles" feature class with the coordinate system set to WGS84 + NGVD1929.
	@type cursor29: arcpy.InsertCursor
	@return: Returns the currency date (or None if unsuccessful).
	@rtype: datetime.date
	@raise IOError: Raised if dofPath does not exist.
	"""
	if not os.path.exists(dofPath):
		raise IOError("File not found: %s" % dofPath)
	
	currencyDate = None
	with open(dofPath) as f:
		cursor = None
		i = 0
		for line in f:
			if i == 0:
				currencyDate = _parseCurrencyDate(line)
			elif i >= 4:
				obstacle = Obstacle(line)
				
				# Choose the correct cursor based on the date
				if obstacle.date < _zDate:
					cursor = cursor29
				else:
					cursor = cursor88
					
				row = cursor.newRow()
				addObstacleToRow(row, obstacle)
				cursor.insertRow(row)
			i += 1
	return currencyDate

def readDofsIntoGdb(gdbPath, dofPaths):
	"""Reads DOF file into file geodatabase.
	@param gdbPath: Path to the GDB.
	@param dofPaths: Paths to DOF files
	"""
	featureClassPath = os.path.join(gdbPath, "Obstacles")
	# Because of the differing vertical coordinate systems, two cursors need to be created.
	cursor88 = arcpy.InsertCursor(featureClassPath)
	cursor29 = arcpy.InsertCursor(featureClassPath, "%s,%s" % (_wgs84, _ngvd1929))
	for dofPath in dofPaths:
		_readDofIntoGdb(dofPath, cursor88, cursor29)
	del cursor88, cursor29



def main(argv=None):
	"""This method will be run if this file is run as a script (as opposed to a module).
	"""
	
	if argv is None:
		argv = sys.argv
		
	print "Downloading DOFs..."
	dofFilePaths = downloadDofs();
	
	# Get the parameter for the output GDB.
	if len(argv) > 1:
		gdbPath = os.path.abspath(arcpy.GetParameterAsText(1))
	else:
		gdbPath = os.path.abspath("../../FaaObstruction.gdb")
	
	print "Creating new geodatabase: %s..." % gdbPath
	createDofGdb(gdbPath)
	
	print "Importing data from..."
	readDofsIntoGdb(gdbPath, dofFilePaths)
	
	print "Finished"

	
if __name__ == "__main__":
	main()
	##downloadDofs()