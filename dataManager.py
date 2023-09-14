from pathvalidate import sanitize_filename
from tempfile import TemporaryDirectory
from shutil import copy2, copytree
from sys import stdout as sysStdout
from io import StringIO
from PIL import Image
import subprocess
import platform
import winreg
import shlex
import json
import os

# import type defs
from collections.abc import Mapping, Sequence, Callable
from typing import Any
from os import PathLike

# since app is intended to be run in a different working dir, CURRENT_FILE_DIR is needed for accessing certain data
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
#---------------------------------------------------------------------------------------------------
class DataManager():
	def __init__(self, basePath: PathLike, packLayoutPath: PathLike, assetTypeTablePath: PathLike, packAdditionsFolder: PathLike, packerPath: PathLike | None) -> None:
		
		# paths
		self.basePath           = basePath
		self.packLayoutPath     = packLayoutPath
		self.assetTypeTablePath = assetTypeTablePath
		self.packAdditionsDir   = packAdditionsFolder
		self.defaultImgPath     = os.path.join(CURRENT_FILE_DIR, 'images\\defaultImage.png')

		self.packerPath = None
		self.UEDir      = None
		
		# verify / get the path to UnrealPak.exe
		if packerPath != None:
			if os.path.exists(os.path.abspath(packerPath)):
				self.packerPath = os.path.abspath(packerPath)
				self.UEDir = os.path.abspath(os.path.join(packerPath, '../../../../'))
		else:
			# try to get paths if not provided / invalid (windows only only)
			self._getEnginePaths()

		# throw approprate error
		if self.packerPath == None:
			raise FileNotFoundError('Unable to determine a valid path to UnrealPak.exe\nVerify that UnrealEngine is installed and that if a path is provided it is valid.')

		# get data from json files
		self.packLayout     = self.fetchJsonData(self.packLayoutPath)
		self.assetTypeTable = self.fetchJsonData(self.assetTypeTablePath)

		# init other vars
		self.tmpDir = None
		self.tmpPackPath = None
		self.tmpFilePaths: Mapping[str, tuple[PathLike[str], str] | None] = {}
		
		self.packInfo: Mapping[str, Any] = {
			'packName':        None,
			'packCleanName':   None,
			'packVersion':     None,
			'packDesc':        '', # optional
			'packCategory':    None,
			'packTags':        '', # optional
			'packAssetsPath':  None,
			'packThumbPath':   '', # optional
			'packScrShotPath': '', # optional
			'packOutputPath':  None,
			'packAssetTypes':  set(),
		}

		self.manifestData   = None
		self.configData     = None
		self.responseData   = None
		self.packingCmdData = None

		self.activeJobs:  list[tuple[subprocess.Popen, str]] = [] # tuple(running subprocess, process type)
		self.failedJobs:  list[tuple[subprocess.Popen, str]] = [] # tuple(finished subprocess, process type)
		self.pendingJobs: list[tuple[tuple[Callable[[], subprocess.Popen], str], set[str]]] = [] # tuple(subprocess callable -> activeJobTuple, "waiting on" process type)
		self.jobStdout: Mapping[int, StringIO] = {} # dict(subprocess PID: subprocess STDOUT so far)

		self.onCleanupFuncs: list[Callable[[], None]] = [] # list of functions to execute when cleaning up

#---
# user data management

	def setPackInfo(self, packName: str | None = None, version: str | None = None, descrition: str | None = None, category: str | None = None, tags: str | None = None, assetTypes: list[str] | None = None , assetsPath: PathLike[str] | None = None, tumbnailPath: PathLike[str] | None = None, screenshotPath: PathLike[str] | None = None, outputPath: PathLike[str] | None = None) -> None:
		""" Set packInfo values. """

		if packName and isinstance(packName, str):
			self.packInfo['packName'] = packName
			self.packInfo['packCleanName'] = sanitize_filename(packName.replace(' ', '_'), replacement_text='_')
		else:
			self.packInfo['packName'] = None
			self.packInfo['packCleanName'] = None

		if version and isinstance(version, str):
			self.packInfo['packVersion'] = version

		if descrition != None and isinstance(descrition, str):
			self.packInfo['packDesc'] = descrition

		if category and isinstance(category, str):
			self.packInfo['packCategory'] = category

		if tags != None and isinstance(tags, str):
			self.packInfo['packTags'] = tags

		if assetTypes and isinstance(assetTypes, list):
			self.packInfo['packAssetTypes'] = assetTypes

		if assetsPath and isinstance(assetsPath, str):
			if os.path.exists(assetsPath):
				self.packInfo['packAssetsPath'] = assetsPath
			else:
				self.packInfo['packAssetsPath'] = None

		if tumbnailPath != None and isinstance(tumbnailPath, str):
			if os.path.exists(tumbnailPath):
				self.packInfo['packThumbPath'] = tumbnailPath
			else:
				self.packInfo['packThumbPath'] = ''

		if screenshotPath != None and isinstance(screenshotPath, str):
			if os.path.exists(screenshotPath):
				self.packInfo['packScrShotPath'] = screenshotPath
			else:
				self.packInfo['packScrShotPath'] = ''

		if outputPath and isinstance(outputPath, str):
			if os.path.exists(outputPath):
				self.packInfo['packOutputPath'] = outputPath
			else:
				self.packInfo['packOutputPath'] = None

#-
	def getMissingPackInfo(self) -> list | None:
		""" Return a list of all missing data in packInfo. """
		# early out if all good
		if None not in self.packInfo.values():
			return None
		
		# return array of all keys with None values
		missingInfo = [key for key, value in self.packInfo.items() if value == None]

		return missingInfo

#-
	def addAssetTypes(self, types: Sequence[str]) -> None:
		""" Manually add asset types to stored list. """

		self.packInfo['packAssetTypes'].update(types)

#-
	def generateFileData(self) -> None:
		""" Generate all file data needed to create a pack.\n
		NOTE: Data stored in mem, see createPack or writeDataToTmpPack for disk write
		"""

		self.generatePackFileStruct()
		self._generateManifestData()
		self._generateConfigData()
		self._generateResponseData()

#-
	def createPack(self, exportCompressedPack: bool, exportPackStruct: bool, InstallToEngine: bool) -> None:
		""" Create a pack given already generated file data (see generateFileData). """

		self.writeDataToTmpPack()
		self.generateUpack()

		if exportCompressedPack:
			self.exportCompressedPack()

		if exportPackStruct:
			self.exportPackStruct()

		if InstallToEngine:
			self.exportContentToEngine()
		else:
			upackPath = os.path.join(self.UEDir, 'FeaturePacks', self.tmpFilePaths["upackFile"][1])
			self.onCleanupFuncs.append(lambda: os.unlink(upackPath))

#---
# file data generation

	def _generateManifestData(self) -> None:
		""" Generate a manifest file to be used by .unrealPak.exe . """

		self.manifestData = {
			'Version': self.packInfo['packVersion'],
			'Name':
			[
				{
					'Language': 'en',
					'Text': self.packInfo['packName']
				},
			],
			'Description':
			[
				{
					'Language': 'en',
					'Text': self.packInfo['packDesc']
				},
			],
			'AssetTypes':
			[
				{
					'Language': 'en',
					'Text': ', '.join(self.packInfo['packAssetTypes'])
				},
			],
			'SearchTags':
			[
				{
					'Language': 'en',
					'Text': self.packInfo['packTags']
				},
			],
			'ClassTypes': '',
			'Category': self.packInfo['packCategory'],
			'Thumbnail': self.tmpFilePaths['thumbnailFile'][1],
			'Screenshots':
			[
				self.tmpFilePaths['screenshotFile'][1],
			]
		}

#-
	def _generateConfigData(self) -> None:
		""" Generate a .config file to be used by .unrealPak.exe . """
		# all paths are rel to UEDir
		self.configData = '\n'.join([
			'[AdditionalFilesToAdd]',
			f'+Files=Samples/{self.packInfo["packCleanName"]}/Content/*.*'
		])

#-
	def _generateResponseData(self) -> None:
		""" Generate a response file to be used by .unrealPak.exe . """

		self.responseData = '\n'.join([
			os.path.relpath(self.tmpFilePaths['configFile'][0], os.path.join(self.packerPath, '../')) + '\\',
			os.path.relpath(self.tmpFilePaths['thumbnailFile'][0], os.path.join(self.packerPath, '../')) + '\\',
			os.path.relpath(os.path.join(self.tmpFilePaths['manifestFile'][0], self.tmpFilePaths['manifestFile'][1]), os.path.join(self.packerPath, '../')),
		])

#-
	def _generatePackingCmdData(self) -> None:
		""" Generate a .bat file for easy packing of outputed pack structure. """

		self.packingCmdData = '\n'.join([
			'@echo off',
			'REM extract output name from dir name',
			'FOR /F %%q IN ("%~dp0.") DO SET "OutputBasename=%%~nxq"',
			'REM get normalized output path',
			rf'SET OutputPath=%~dp0%OutputBasename%.zip',
			'FOR /F "delims=" %%F IN ("%OutputPath%") DO SET "OutputPath=%%~fF"',
			'echo packing...',
			'echo ----------',
			rf'"{self.packerPath}" -Create="%~dp0{self.tmpFilePaths["responseFile"][1]}" "..\..\..\FeaturePacks\{self.tmpFilePaths["upackFile"][1]}"',
			'echo packing Done.',
			'echo.',
			'echo exporting...',
			rf'robocopy "{self.UEDir}\FeaturePacks" "%~dp0ZipContent\FeaturePacks" {self.tmpFilePaths["upackFile"][1]} /w:5',
			'echo exporting Done.',
			'echo archiving...',
			'echo ----------',
			rf'powershell Compress-Archive -Path "%~dp0ZipContent\*" -DestinationPath "%OutputPath%" -Force',
			'echo archiving Done.',
			'echo.',
			'echo zipped pack path: %OutputPath%',
			'pause',
		])

#---
# disk ops

	def InferAssetTypes(self) -> list | None:
		""" Attemts to gather all .uasset types (based on UE's naming conventions).\n
		Returns list of filenames that could not be determined.
		"""

		unkownTypedFiles = []
		for _, _, filenames in os.walk(top=self.packInfo['packAssetsPath']):
			for filename in filenames:
				if not filename.endswith('.uasset'):
					continue
				
				prefixEndIndex = filename.find('_') + 1
				if prefixEndIndex >= 1:
					assetType = self.assetTypeTable.get(filename.upper()[:prefixEndIndex], None)
					if assetType != None:
						# found a valid prefix
						self.packInfo['packAssetTypes'].add(assetType)
						continue
				# coundn't find a valid prefix
				unkownTypedFiles.append(filename)
		if len(unkownTypedFiles):
			return unkownTypedFiles
		else:
			return None

#-
	def generatePackFileStruct(self) -> None:
		""" Generate file structure for the pack in a tmp dir\n
		Populates self.tmpFilePaths, self.tmpDir and self.tmpPackPath vars
		"""

		# sub functions
		@staticmethod
		def _recursiveCreateDir(dirStruct: dict, baseDir: PathLike[str], pathDict: dict) -> None:
			for item in dirStruct:
				if isinstance(dirStruct[item], dict):
					os.mkdir(os.path.join(baseDir, item))
					_recursiveCreateDir(dirStruct[item], os.path.join(baseDir, item), pathDict)
				elif isinstance(dirStruct[item], str):
					pathDict[item] = (baseDir, dirStruct[item])

		# main function

		# hard coding associations is not ideal but necessary for verifications later on
		# tuples: inintaly (path, file/dir pattern), converted to (path, file/dir name)
		self.tmpFilePaths = {
			'configFile':     None,
			'thumbnailFile':  None,
			'screenshotFile': None,
			'manifestFile':   None,
			'upackFile':      None,
			'assetFolder':    None,
			'responseFile':   None,
			'packingCmdFile': None,
		}

		# create tmp dir in UEDir (due to rel path restrictions)
		self.tmpDir = TemporaryDirectory(prefix='unrealPackGen_tmp_', dir=self.UEDir)
		self.onCleanupFuncs.append(self.tmpDir.cleanup)
		self.tmpPackPath = os.path.join(self.tmpDir.name, self.packInfo['packCleanName'])
		os.mkdir(self.tmpPackPath)
		# create pack dir tree in tmp dir
		_recursiveCreateDir(self.packLayout, self.tmpPackPath, self.tmpFilePaths)

		# verify all paths found
		for item in self.tmpFilePaths:
			if self.tmpFilePaths[item] == None:
				raise ValueError(f'{os.path.basename(self.packLayoutPath)} is missing item: {item}')

		# convert patterns to names
		for key in self.tmpFilePaths:
			# account for cases where original name is needed
			match key:
				case 'assetFolder':
					# create dirs from dir pattern (to format used by internal pack layouts), update self.tmpFilePaths entry with new path
					newPath = os.path.join(self.tmpFilePaths[key][0], self.getFilenameFromPattern(key, self.tmpFilePaths[key][1], self.packInfo['packAssetsPath']))
					self.tmpFilePaths[key] = (os.path.normpath(newPath), '')
				case 'thumbnailFile':
					if self.packInfo['packThumbPath']:
						self.tmpFilePaths[key] = (self.tmpFilePaths[key][0], self.getFilenameFromPattern(key, self.tmpFilePaths[key][1], self.packInfo['packThumbPath']))
					else:
						# set to empty str if not provided
						self.tmpFilePaths[key] = (self.tmpFilePaths[key][0], '')
				case 'screenshotFile':
					if self.packInfo['packScrShotPath']:
						self.tmpFilePaths[key] = (self.tmpFilePaths[key][0], self.getFilenameFromPattern(key, self.tmpFilePaths[key][1], self.packInfo['packScrShotPath']))
					else:
						# set to empty str if not provided
						self.tmpFilePaths[key] = (self.tmpFilePaths[key][0], '')
				# default
				case _:
					self.tmpFilePaths[key] = (self.tmpFilePaths[key][0], self.getFilenameFromPattern(key, self.tmpFilePaths[key][1], None))

		# create new dirs for assetFolder
		os.makedirs(self.tmpFilePaths['assetFolder'][0])

#-
	def writeDataToTmpPack(self) -> None:
		""" Write all generated file data to tmp structure.\n
		Additionally copy all other required files from their user specified paths.
		"""

		# ensure all data is available
		if self.manifestData  == None:
			self._generateManifestData()
		if self.configData  == None:
			self._generateConfigData()
		if self.responseData == None:
			self._generateResponseData()
		if self.packingCmdData  == None:
			self._generatePackingCmdData()

		# manifestFile
		with open(os.path.join(self.tmpFilePaths['manifestFile'][0], self.tmpFilePaths['manifestFile'][1]), 'w') as file:
			json.dump(self.manifestData, file, indent=2)

		# configFile
		with open(os.path.join(self.tmpFilePaths['configFile'][0], self.tmpFilePaths['configFile'][1]), 'w') as file:
			file.write(self.configData)

		# responseFile
		with open(os.path.join(self.tmpFilePaths['responseFile'][0], self.tmpFilePaths['responseFile'][1]), 'w') as file:
			file.write(self.responseData)

		# packingCmdFile
		with open(os.path.join(self.tmpFilePaths['packingCmdFile'][0], self.tmpFilePaths['packingCmdFile'][1]), 'w') as file:
			file.write(self.packingCmdData)

		# thumbnailFile / screenshotFile
		# resize to proper size and write to dest. does not write if image not provided
		if self.packInfo['packThumbPath']:
			with Image.open(self.packInfo['packThumbPath']) as originalImage:
				self.cropAndResizeImage(originalImage, (64, 64)).save(os.path.join(self.tmpFilePaths['thumbnailFile'][0] , self.tmpFilePaths['thumbnailFile'][1]))
		if self.packInfo['packScrShotPath']:
			with Image.open(self.packInfo['packScrShotPath']) as originalImage:
				self.cropAndResizeImage(originalImage, (400, 200)).save(os.path.join(self.tmpFilePaths['screenshotFile'][0] , self.tmpFilePaths['screenshotFile'][1]))
		
		# assetFolder
		copytree(self.packInfo['packAssetsPath'], self.tmpFilePaths['assetFolder'][0], dirs_exist_ok=True)

		# packAdditions
		copytree(os.path.normpath(self.packAdditionsDir), os.path.join(self.tmpPackPath, 'ZipContent'), dirs_exist_ok=True)

#-
	def generateUpack(self) -> None:
		""" Create .upack file, outputs to engine's FeaturePacks dir. """

		shellCmd = fr'"{self.packerPath}" -Create="{os.path.join(self.tmpFilePaths["responseFile"][0], self.tmpFilePaths["responseFile"][1])}" "..\..\..\FeaturePacks\{self.tmpFilePaths["upackFile"][1]}"'
		packJob = subprocess.Popen(shlex.split(shellCmd), cwd=os.path.abspath(self.basePath), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

		shellCmd = fr'robocopy "{os.path.join(self.UEDir, "FeaturePacks/")}" "{self.tmpFilePaths["upackFile"][0]}" {self.tmpFilePaths["upackFile"][1]} /e /w:5'
		copyJob = lambda: subprocess.Popen(shlex.split(shellCmd), cwd=os.path.abspath(self.basePath), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

		self.activeJobs.append((packJob, 'unrealpak'))
		self.pendingJobs.append(((copyJob, 'robocopy'), {'unrealpak'}))

#-
	def exportCompressedPack(self) -> None:
		""" Compress and export pack to specified output dir. """

		outputFilePath = os.path.join(self.packInfo['packOutputPath'], f'{self.packInfo["packCleanName"]}.zip')
		shellCmd = fr'powershell Compress-Archive -Path ".\ZipContent\*" -DestinationPath "{outputFilePath}" -Force'
		archiveJob = lambda: subprocess.Popen(shlex.split(shellCmd), cwd=os.path.abspath(self.tmpPackPath), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
		
		self.pendingJobs.append(((archiveJob, 'archive'), {'robocopy', 'unrealpak'}))

#-
	def exportPackStruct(self) -> None:
		""" Export folder structure from tmp dir to specified output dir. """

		self.onCleanupFuncs.append(self.updateExportedResponseFile)
		shellCmd = fr'robocopy "{os.path.abspath(self.tmpDir.name)}" "{self.packInfo["packOutputPath"]}" * /e /w:5'
		copyJob = lambda: subprocess.Popen(shlex.split(shellCmd), cwd=os.path.abspath(self.tmpDir.name), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

		self.pendingJobs.append(((copyJob, 'robocopy'), {'robocopy', 'unrealpak'}))

#-
	def updateExportedResponseFile(self) -> None:
		""" Update the path in the response file to work in new dir. """
		
		filePath = os.path.join(self.packInfo["packOutputPath"], os.path.relpath(self.tmpFilePaths['responseFile'][0], self.tmpDir.name), self.tmpFilePaths['responseFile'][1])
		oldDirPath = os.path.relpath(self.tmpPackPath, os.path.join(self.packerPath, '../'))
		newDirPath = os.path.abspath(os.path.join(filePath, '../'))

		with open(filePath, 'r') as file:
			oldResponseData = file.read()
		
		newResponseData = oldResponseData.replace(oldDirPath, newDirPath)

		with open(filePath, 'w') as file:
			file.write(newResponseData)

#-
	def exportContentToEngine(self) -> None:
		""" Copy Samples folder from the tmp dir to engine's. """

		dirKeyword = 'Samples'
		endIndex = self.tmpFilePaths['assetFolder'][0].rfind(dirKeyword) + len(dirKeyword)
		shellCmd = fr'robocopy "{self.tmpFilePaths["assetFolder"][0][:endIndex]}" "{os.path.join(self.UEDir, "Samples")}" * /e /w:5'
		copyJob = subprocess.Popen(shlex.split(shellCmd), cwd=os.path.abspath(self.tmpDir.name), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

		self.activeJobs.append((copyJob, 'robocopy'))

#---
# subprocess job management

	def pollJobs(self, noStdOut: bool = False) -> (int, int):
		""" Process both active and pending jobs\n
		Returns: (activeJobCount, pendingJobCount)
		"""

		self.pollActiveJobs(noStdOut)
		self.pollPendingJobs()
		return (self.getActiveJobCount(), self.getPendingJobCount())

#-
	def pollActiveJobs(self, noStdOut: bool = False) -> int:
		""" Process all active jobs that have finished since the last call.\n
		Optinally outputs stored STDOUT into console.\n
		Return the number of active jobs.
		"""

		# sub function
		@staticmethod
		def _isSuccessExitCode(exitcode: int, jobType: str) -> bool:
			if jobType == 'robocopy':
				return bool(exitcode <= 7)
			if jobType == 'unrealpak':
				return bool(exitcode == 0)
			if jobType == 'archive':
				return bool(exitcode == 0)

		# main function
		for i, job in enumerate(self.activeJobs):
			# dump PIPE buffer to stringio
			self.writeJobOutToStream(job[0])
			# get/process exited processes
			exitCode = job[0].poll()
			if exitCode is None:
				continue
			else:
				# remove from active jobs
				self.activeJobs[i] = None
				if not _isSuccessExitCode(exitCode, job[1]):
					self.failedJobs.append(job)

				if noStdOut:
					self.jobStdout[job[0].pid].close()
					self.jobStdout[job[0].pid] = None
				else:
					print('===============================================================================')
					print('outputing subprocess info:\n')
					self.writeStoredJobOutToConsole(job[0])

		# removes finshed jobs from activeJobs
		self.activeJobs = [job for job in self.activeJobs if job is not None]
		return self.getActiveJobCount()

#-
	def pollPendingJobs(self) -> int:
		""" Process pending jobs, adding them to the active job list if no longer waiting on any other job(s). """
		activeJobTypes: set[str] = set()
		for activeJob in self.activeJobs:
			activeJobTypes.add(activeJob[1])

		for i, job in enumerate(self.pendingJobs):
				if job[1].isdisjoint(activeJobTypes):
					# start to run the subprocess
					activatedJob = (job[0][0](), job[0][1])
					# add to active jobs and add the job type to activeJobTypes
					self.activeJobs.append(activatedJob)
					activeJobTypes.add(activatedJob[1])
					# prep for removal
					self.pendingJobs[i] = None

		# removes no longer pending jobs from pendingJobs
		self.pendingJobs = [job for job in self.pendingJobs if job is not None]
		return self.getPendingJobCount()

#-
	def getActiveJobCount(self) -> int:
		""" Return the number of active jobs. """
		return len(self.activeJobs)

#-
	def getPendingJobCount(self) -> int:
		""" Return the number of pending jobs. """
		return len(self.pendingJobs)

#-
	def getFailedJobTypes(self) -> list[str] | None:
		""" Return a list of subprocess types. """

		# early out in no failed jobs
		if not len(self.failedJobs):
			return None
		# unique list of jobTypes
		return list({jobType for job, jobType in self.failedJobs})

#-
	def writeJobOutToStream(self, job: subprocess.Popen) -> StringIO:
		""" Write a subprocess' STDOUT into temporary text buffer.\n
		Create buffer if not already present.
		"""

		storedOutput = self.jobStdout.get(job.pid, None)
		# create if first write
		if storedOutput == None:
			storedOutput = self.jobStdout[job.pid] = StringIO()

		for line in job.stdout:
			storedOutput.write(line.decode('utf-8'))

		return storedOutput

#-
	def writeStoredJobOutToConsole(self, job: subprocess.Popen, closeOnComplete: bool = True) -> None:
		""" Output the stored subprocess' STDOUT into the console.\n
		Optionally close the buffer used to store the STDOUT.
		"""

		# get stringIO
		storedoutput = self.jobStdout.get(job.pid, None)
		if storedoutput == None:
			storedoutput = self.writeJobOutToStream(job)
		# write to console
		sysStdout.write(storedoutput.getvalue())

		# close and remove ref for GC
		if closeOnComplete:
			storedoutput.close()
			self.jobStdout[job.pid] = None

#---
# other

	def cleanup(self) -> None:
		""" Execute all functions present in the onCleanupFuncs list (LIFO). """

		while len(self.onCleanupFuncs):
			func = self.onCleanupFuncs.pop()
			func()
		self.onCleanupFuncs.clear()

#-
	def openOutputDir(self) -> None:
		""" Open output dir in file explorer. """
		print(os.path.normpath(self.packInfo["packOutputPath"]))
		subprocess.Popen(shlex.split(f'explorer "{os.path.normpath(self.packInfo["packOutputPath"])}"'))

#-
	def getFilenameFromPattern(self, fileKey: str, pattern: str | None, originalFilePath: PathLike[str] | None) -> str | None:
		""" Return a name given a specific pattern. """

		# sub function
		@staticmethod
		def _recursiveSearch(obj, key) -> Any | None:
			if key in obj:
				return obj[key]
			#else
			for item in obj:
				if isinstance(obj[item], dict):
					keyValue = _recursiveSearch(obj[item], key)
					if keyValue != None:
						return keyValue

		# main function
		# find pattern if its not already provided
		if pattern == None:
			pattern = _recursiveSearch(self.packLayout, fileKey)

		if originalFilePath == None:
			basename = ext = None
		else:
			# convert to abs removing ending slashes & dots > get last segement > split out basename and ext
			basename, ext = os.path.splitext(os.path.basename(os.path.abspath(originalFilePath)))

		return pattern.format(
			PACKNAME = self.packInfo['packCleanName'] or '',
			BASENAME = basename or '',
			EXT      = ext or '',
		)

#-
	def _getEnginePaths(self) -> bool:
		""" Attempt to determine the location of a valid unreal install, as well as the unrealpak.exe countained within.\n
		returns success
		"""

		if platform.system() != 'Windows':
			return False
		
		PackerRelPath = r'.\Engine\Binaries\Win64\UnrealPak.exe'
		UESubkeyPath = r'SOFTWARE\EpicGames\Unreal Engine\\'

		with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UESubkeyPath) as UEKey:
			# iterate over all subkeys (ie: versions)
			availableVersions = []
			for i in range(0, winreg.QueryInfoKey(UEKey)[0]):
				versionName = winreg.EnumKey(UEKey, i)
				availableVersions.append(versionName)
			# order by version

			# in theory, should be ordered newest version last, in theory...
			for version in reversed(availableVersions):
				with winreg.OpenKey(UEKey, version) as versionKey:
					# iterate over values
					for i in range(0, winreg.QueryInfoKey(versionKey)[1]):
						valueName, valueData, _, = winreg.EnumValue(versionKey, i)
						# find value containing install path, verify it exists
						if valueName == 'InstalledDirectory':
							if os.path.exists(os.path.abspath(os.path.join(valueData, PackerRelPath))):
								# return: abs engine path, abs packer path
								self.UEDir = os.path.abspath(valueData)
								self.packerPath = os.path.abspath(os.path.join(valueData, PackerRelPath))
								return True
		return False

#-
	@classmethod
	def cropAndResizeImage(cls, image: Image.Image, targetSize: tuple[int, int]) -> Image.Image:
		if (targetSize[0] / targetSize[1]) <= (image.width / image.height):
			cropHeight = image.height
			cropWidth  = image.height * (targetSize[0] / targetSize[1])
		else:
			cropHeight = image.width * (targetSize[1] / targetSize[0])
			cropWidth  = image.width

		cropBbox = (
			(image.width *0.5) - (cropWidth *0.5),
			(image.height*0.5) - (cropHeight*0.5),
			(image.width *0.5) - (cropWidth *0.5) + cropWidth,
			(image.height*0.5) - (cropHeight*0.5) + cropHeight,
			)

		return image.resize(targetSize, Image.BICUBIC, cropBbox)

#-
	@classmethod
	def fetchJsonData(cls, filePath: PathLike[str] | str) -> dict | None:
		try:
			with open(filePath) as file:
				data = json.load(file)
			return data
		except:
			return None

#---
	def __del__(self) -> None:
		""" Attempt to cleanup as much as possible in the event of non standard exit. """

		self.cleanup()