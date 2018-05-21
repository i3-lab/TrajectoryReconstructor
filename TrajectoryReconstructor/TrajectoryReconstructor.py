import os
import unittest
import time
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from functools import partial
import CurveMaker, numpy
import csv
#------------------------------------------------------------
#
# Locator
#
class TrajectoryReconstructor(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "TrajectoryReconstructor" # TODO make this more human readable by adding spaces
    self.parent.categories = ["IGT"]
    self.parent.dependencies = ["Sequences"]
    self.parent.contributors = ["Longquan Chen(BWH), Junichi Tokuda(BWH)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    Trajectory path reconstruction based on tracking data.
    """
    self.parent.acknowledgementText = """
    This work is supported by NIH National Center for Image Guided Therapy (P41EB015898).
    """ 
    # replace with organization, grant and thanks.


#------------------------------------------------------------
#
# TrajectoryReconstructorWidget
#
class TrajectoryReconstructorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  REL_SEQNODE = "vtkMRMLSequenceBrowserNode.rel_seqNode"
  REL_LOCATORINDEX_FIDUCIAL = "vtkMRMLMarkupsFiducialNode.rel_locatorIndex"
  REL_LOCATORINDEX_MODEL = "vtkMRMLModelNode.rel_locatorIndex"
  REL_LOCATORINDEX_SEQ = "vtkMRMLSequenceNode.rel_locatorIndex"
  REL_LOCATOR = "vtkMRMLLinearTranformNode.rel_locator"
  #REL_TRAJECTORYINDEX_TRANS = "vtkMRMLLinearTranformNode.rel_trajectoryIndex"
  REL_TRAJECTORYINDEX_SEQ = "vtkMRMLSequenceNode.rel_trajectoryIndex"
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...
    self.nLocators = 5
    self.logic = TrajectoryReconstructorLogic(self, self.nLocators)
    self.logic.setWidget(self)
    self.elementPerLocator = 6
    self.exportDirString = ""
    self.importDirString = ""
    self.fileString = ""
    self.maximumFileNameLen = 20
    self.processVariance = 5e-5
    self.measurementVariance = 0.0004
    self.movementThreshold = 1.0 # in millimeter
    self.downSampleStepSize = 10

    self.sequenceBrowserWidget = slicer.modules.sequencebrowser.widgetRepresentation()
    self.replayButton = self.sequenceBrowserWidget.findChild("QPushButton","pushButton_VcrPlayPause")
    self.recordButton = self.sequenceBrowserWidget.findChild("QPushButton","pushButton_VcrRecord")
    self.sequenceNodeComboBox = self.sequenceBrowserWidget.findChild("qMRMLNodeComboBox","MRMLNodeComboBox_SynchronizeSequenceNode")
    self.addSequenceNodeButton = self.sequenceBrowserWidget.findChild("QPushButton","pushButton_AddSequenceNode")
    self.removeSequenceNodeButton = self.sequenceBrowserWidget.findChild("QPushButton","pushButton_RemoveSequenceNode")
    self.sequenceNodeCellWidget = self.sequenceBrowserWidget.findChild("QTableWidget", "tableWidget_SynchronizedSequenceNodes")
    self.recordingSamplingSetting = self.sequenceBrowserWidget.findChild("QComboBox", "comboBox_RecordingSamplingMode")

    if (self.sequenceBrowserWidget is None) or (self.replayButton is None) or (self.recordButton is None) or \
       (self.sequenceNodeComboBox is None) or (self.addSequenceNodeButton is None) or (self.removeSequenceNodeButton is None) or \
       (self.sequenceNodeCellWidget is None) or (self.recordingSamplingSetting is None) :
      return slicer.util.warningDisplay(
        "Error: Could not load SequenceBrowser widget. either Extension is missing or the API of SequenceBrowser is changed.")

    #
    #--------------------------------------------------


    #--------------------------------------------------
    # GUI components

    #
    # Connector Create and Interaction
    #
    self.openIGTLinkIFWidget = slicer.modules.openigtlinkif.widgetRepresentation()
    self.connectorCollapsibleButton = self.openIGTLinkIFWidget.findChild("ctkCollapsibleButton", "ConnectorListFrame")
    if self.connectorCollapsibleButton is None:
      return slicer.util.warningDisplay(
        "Error: Could not load OpenIGTLink widget. either Extension is missing or the API of OpenIGTLink is changed.")
    else:
      self.layout.addWidget(self.connectorCollapsibleButton)
    #
    # Registration Matrix Selection Area
    #

    #
    # Algorithm setting section
    #
    self.algorithmSettingCollapsibleButton = ctk.ctkCollapsibleButton()
    self.algorithmSettingCollapsibleButton.text = "Algorithm Settings"
    self.algorithmSettingCollapsibleButton.setChecked(False)
    self.layout.addWidget(self.algorithmSettingCollapsibleButton)
    self.settingFormLayout = qt.QFormLayout(self.algorithmSettingCollapsibleButton)
    self.realTimeReconstructCheckBox = qt.QCheckBox()
    self.realTimeReconstructCheckBox.setChecked(True)
    self.processVarianceSpinBox = qt.QDoubleSpinBox()
    self.processVarianceSpinBox.setDecimals(6)
    self.processVarianceSpinBox.setValue(5e-5)
    self.processVarianceSpinBox.setSingleStep(1e-5)
    self.processVarianceSpinBox.setToolTip("Related to the pocess noise level")
    self.processVarianceSpinBox.connect('valueChanged(double)', self.onProcessVarianceChanged)
    self.measurementVarianceSpinBox = qt.QDoubleSpinBox()
    self.measurementVarianceSpinBox.setDecimals(4)
    self.measurementVarianceSpinBox.setValue(0.001)
    self.measurementVarianceSpinBox.setSingleStep(0.001)
    self.measurementVarianceSpinBox.setToolTip("Related to the measurement noise level")
    self.measurementVarianceSpinBox.connect('valueChanged(double)', self.onMeasurementVarianceChanged)
    self.movementThresholdSpinBox = qt.QDoubleSpinBox()
    self.movementThresholdSpinBox.setValue(1.0)
    self.movementThresholdSpinBox.setDecimals(2)
    self.movementThresholdSpinBox.setMinimum(0.0)
    self.movementThresholdSpinBox.setSingleStep(0.5)
    self.movementThresholdSpinBox.setToolTip("The threshold for needle movement to be sampled. \
                                              A moving window with certain size will process the data and only add the data to the downsample sequence \
                                              if the distance to the previouse window section is larger than the threshold")
    self.movementThresholdSpinBox.connect('valueChanged(double)', self.onMovementThresholdChanged)
    self.downSampleStepSizeSpinBox = qt.QSpinBox()
    self.downSampleStepSizeSpinBox.setValue(10)
    self.downSampleStepSizeSpinBox.setMinimum(1)
    self.downSampleStepSizeSpinBox.setSingleStep(1)
    self.downSampleStepSizeSpinBox.setToolTip("Moving window size for downsampling, this variable is used in combination with the movement threshold")
    self.downSampleStepSizeSpinBox.connect('valueChanged(double)', self.onDownSampleStepSizeChanged)

    self.savingSeperateChannelCheckBox = qt.QCheckBox()
    self.savingSeperateChannelCheckBox.connect(qt.SIGNAL("clicked()"), self.onSavingSeperateChannel)
    self.savingSeperateChannelCheckBox.setToolTip("When this check box is checked, tracking data in different channel will be saved in different files.")
    self.removeDuplicatePosCheckBox = qt.QCheckBox()
    self.settingFormLayout.addRow("Real-time Reconstruct: ", self.realTimeReconstructCheckBox)
    self.settingFormLayout.addRow("Process Variance: ", self.processVarianceSpinBox)
    self.settingFormLayout.addRow("Measurement Variance: ", self.measurementVarianceSpinBox)
    self.settingFormLayout.addRow("Movement Threshold: ", self.movementThresholdSpinBox)
    self.settingFormLayout.addRow("Downsample Window Size: ", self.downSampleStepSizeSpinBox)
    self.settingFormLayout.addRow("SeperateFiles: ", self.savingSeperateChannelCheckBox)
    self.settingFormLayout.addRow("Remove Duplicated Positions: ", self.removeDuplicatePosCheckBox)

    self.selectionCollapsibleButton = ctk.ctkCollapsibleButton()
    self.selectionCollapsibleButton.text = "Locator ON/OFF"
    self.layout.addWidget(self.selectionCollapsibleButton)
    self.selectionFormLayout = qt.QFormLayout(self.selectionCollapsibleButton)
    self.transformSelector = []
    self.locatorRecordCheckBox = []
    self.trajectoryIndexSpinBox = []
    self.trajectoryIndexSpinBoxLastValue = []
    self.locatorReplayCheckBox = []
    self.locatorRecontructButton = []
    self.colors = [[0.3, 0.5, 0.5], [0.2, 0.3, 0.6], [0.1, 0.6, 0.5], [0.5, 0.9, 0.5], [0.0, 0.2, 0.8]]
    for i in range(self.nLocators):
      self.transformSelector.append(slicer.qMRMLNodeComboBox())
      transSelector = self.transformSelector[i]
      transSelector.nodeTypes = ( ("vtkMRMLLinearTransformNode"), "" )
      transSelector.selectNodeUponCreation = True
      transSelector.addEnabled = False
      transSelector.removeEnabled = False
      transSelector.noneEnabled = False
      transSelector.showHidden = False
      transSelector.showChildNodeTypes = False
      transSelector.setMRMLScene( slicer.mrmlScene )
      transSelector.connect("nodeAdded(vtkMRMLNode*)", self.onAddedTransNode)
      transSelector.setToolTip( "Choose a locator transformation matrix" )

      self.locatorRecordCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorRecordCheckBox[i]
      checkbox.checked = 0
      checkbox.text = 'Record: '
      checkbox.setToolTip("Activate locator")
      checkbox.setLayoutDirection(1) # 1 =  QtCore.Qt.RightToLeft
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorRecording, checkbox))

      selectorLayout = qt.QHBoxLayout()
      recordingLayout = qt.QHBoxLayout()
      selectorLayout.addWidget(transSelector)
      recordingLayout.addWidget(checkbox)
      self.trajectoryIndexSpinBox.append(qt.QSpinBox())
      self.trajectoryIndexSpinBoxLastValue.append(-1)
      self.trajectoryIndexSpinBox[i].setValue(0)
      self.trajectoryIndexSpinBox[i].setMinimum(0)
      self.trajectoryIndexSpinBox[i].setSingleStep(1)
      selectorLayout.addWidget(self.trajectoryIndexSpinBox[i])
      self.trajectoryIndexSpinBox[i].connect('valueChanged(int)', partial(self.onTrajectoyIndexChanged, self.trajectoryIndexSpinBox[i]))
      
      self.locatorReplayCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorReplayCheckBox[i]
      checkbox.checked = 0
      checkbox.text = 'Replay: '
      checkbox.setToolTip("Replay locator")
      checkbox.setLayoutDirection(1)  # 1 =  QtCore.Qt.RightToLeft
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorReplay, checkbox))
      recordingLayout.addWidget(checkbox)
      
      self.locatorRecontructButton.append(qt.QPushButton())
      pushbutton = self.locatorRecontructButton[i]
      pushbutton.setCheckable(False)
      pushbutton.text = 'Reconstruct'
      pushbutton.setToolTip("Generate the trajectory based on the tracked needle")
      pushbutton.connect(qt.SIGNAL("clicked()"), partial(self.onConstructTrajectory, pushbutton))
      recordingLayout.addWidget(pushbutton)
      
      self.selectionFormLayout.addRow("Locator #%d:" % (i+1), selectorLayout)
      self.selectionFormLayout.addRow("Locator #%d:" % (i+1), recordingLayout)

    self.exportImportCollapsibleButton = ctk.ctkCollapsibleButton()
    self.exportImportCollapsibleButton.text = "Export/Import Results"
    self.layout.addWidget(self.exportImportCollapsibleButton)
    self.exportImportFormLayout = qt.QFormLayout(self.exportImportCollapsibleButton)
    self.outputDirBrowserButton = qt.QPushButton()
    self.fileDialog = qt.QFileDialog()
    self.fileNameEditor = qt.QLineEdit()
    self.saveButton = qt.QPushButton()
    self.saveButton.setText("Save")
    self.exportLayout = qt.QHBoxLayout()
    self.exportLayout.addWidget(self.outputDirBrowserButton)
    self.saveFileLayout = qt.QHBoxLayout()
    self.saveFileLayout.addWidget(self.fileNameEditor)
    self.saveFileLayout.addWidget(self.saveButton)
    self.outputDirBrowserButton.clicked.connect(self.selectDirectory)
    self.saveButton.clicked.connect(self.saveFile)

    self.inputFileBrowserButton = qt.QPushButton()
    self.inputFileBrowserButton.setText("Input CSV file name")
    self.loadButton = qt.QPushButton()
    self.loadButton.setText("Load")
    self.importLayout = qt.QHBoxLayout()
    self.importLayout.addWidget(self.inputFileBrowserButton)
    self.importLayout.addWidget(self.loadButton)
    self.inputFileBrowserButton.clicked.connect(self.selectForImport)
    self.loadButton.clicked.connect(self.loadFile)

    self.exportImportFormLayout.addRow("Export to directory: ", self.exportLayout)
    self.exportImportFormLayout.addRow("Export File name: ", self.saveFileLayout)
    self.exportImportFormLayout.addRow("Import File: ", self.importLayout)

    self.initialize()

    #--------------------------------------------------
    # connections
    #
    slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartImportEvent, self.StartCaseImportCallback)
    slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndImportEvent, self.LoadCaseCompletedCallback)

    # Add vertical spacer
    self.layout.addStretch(1)

  def initialize(self, sequenceNodesList = None, sequenceBrowserNodesList = None):
    """
    Initialize variables in the widget to be empty lists if either sequence node and sequence browser node are not provided \
    When both sequence node and sequence browser node are provided, add the sequence ralated nodes and contruct the trajectories for all sequences.
    :param sequenceNodesList:
    :param sequenceBrowserNodesList:
    :return: None
    """
    self.trajectoryFidicualsList = [[],[],[],[],[]]
    self.trajectoryModelsList = [[],[],[],[],[]]
    self.curveManagersList = [[],[],[],[],[]]
    self.sequenceNodesList = [[],[],[],[],[]]
    self.sequenceBrowserNodesList = [[],[],[],[],[]]
    self.locatorNodeList = []
    if (sequenceNodesList is not None) and (sequenceBrowserNodesList is not None):
      transformCollection = slicer.mrmlScene.GetNodesByClass("vtkMRMLLinearTransformNode")
      for index in range(transformCollection.GetNumberOfItems()):
        transformNode = transformCollection.GetItemAsObject(index)
        if transformNode.GetAttribute(self.REL_LOCATOR) is not None:
          self.locatorNodeList.append(transformNode)
      for locatorIndex in range(len(sequenceNodesList)):
        for j in range(len(sequenceNodesList[locatorIndex])):
          self.addSequenceRelatedNodesInList(locatorIndex, j, sequenceNodesList[locatorIndex][j], sequenceBrowserNodesList[locatorIndex][j])
      for locatorIndex in range(len(sequenceNodesList)):
        if len(sequenceNodesList[locatorIndex])>0:
          self.onConstructTrajectory(self.locatorRecontructButton[locatorIndex])
    if not self.sequenceBrowserNodesList[0] == []:
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[0][0])

  def cleanup(self):
    for i in range(self.nLocators):
      if self.sequenceNodesList:
        if not self.sequenceNodesList[i] == []:
          numberOfSeq = len(self.sequenceNodesList[i])
          for j in range (numberOfSeq):
            if self.sequenceNodesList and self.sequenceNodesList[i][j]:
              slicer.mrmlScene.RemoveNode(self.sequenceNodesList[i][j])
            if self.sequenceBrowserNodesList and self.sequenceBrowserNodesList[i][j]:
              slicer.mrmlScene.RemoveNode(self.sequenceBrowserNodesList[i][j])
            if self.trajectoryFidicualsList and self.trajectoryFidicualsList[i][j]:
              slicer.mrmlScene.RemoveNode(self.trajectoryFidicualsList[i][j])
            if self.trajectoryModelsList and self.trajectoryModelsList[i][j]:
              slicer.mrmlScene.RemoveNode(self.trajectoryModelsList[i][j])
            if self.curveManagersList and self.curveManagersList[i][j]:
              self.curveManagersList[i][j].clear()
    del self.trajectoryFidicualsList[:]
    del self.sequenceNodesList[:]
    del self.sequenceBrowserNodesList[:]
    del self.trajectoryModelsList[:]
    del self.curveManagersList[:]
    slicer.mrmlScene.Clear(0)
    pass

  def selectDirectory(self):
    """
    Select the directory for data export
    :return: None
    """
    self.exportDirString = self.fileDialog.getExistingDirectory()
    if len(self.exportDirString)>self.maximumFileNameLen:
      self.outputDirBrowserButton.setText(".." + self.exportDirString[-self.maximumFileNameLen:])

  def selectForImport(self):
    """
    Select the directory for data import
    :return:
    """
    if self.savingSeperateChannelCheckBox.checked == True:
      self.importDirString = self.fileDialog.getExistingDirectory()
      if len(self.importDirString) > self.maximumFileNameLen:
        self.inputFileBrowserButton.setText(".." + self.importDirString[-self.maximumFileNameLen:])
    else:
      self.fileString = self.fileDialog.getOpenFileName()
      if len(self.fileString)>self.maximumFileNameLen:
        self.inputFileBrowserButton.setText(".." + self.fileString[-self.maximumFileNameLen:])


  def loadFile(self):
    """
    Load the saved tracked data either from one file or from a directory
    :return: None
    """
    if not slicer.util.confirmYesNoDisplay("Current MRMLScene will be clear. Do you want to proceed?"):
      return
    self.cleanup()
    self.initialize()
    if self.savingSeperateChannelCheckBox.checked == True:
      self.loadFromSeperateFiles()
    else:
      self.loadFromOneFile()
    pass

  def loadFromSeperateFiles(self):
    """
    Load the saved tracked data from a directory
    :return: None
    """
    startLocatorIndex = 0
    for file in os.listdir(self.importDirString):
      self.fileString = os.path.join(self.importDirString, file)
      self.loadFromOneFile(startLocatorIndex)
      startLocatorIndex = startLocatorIndex + 1
    pass

  def loadFromOneFile(self, startLocatorIndex = 0):
    """
    Load the saved tracked data from one file
    :return: None
    """
    if os.path.isfile(self.fileString):
      with open(self.fileString, 'rb') as csvfile:
        fileReader = csv.reader(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        rowIndex = 0
        locatorIndexes = []
        for row in fileReader:
          numTrajectoryInRow = int(len(row) / self.elementPerLocator)
          locatorIndex = startLocatorIndex
          if rowIndex == 0:
            locatorName = row[0]
            transformNode = slicer.vtkMRMLLinearTransformNode()
            slicer.mrmlScene.AddNode(transformNode)
            self.transformSelector[locatorIndex].setCurrentNode(transformNode)
            self.transformSelector[locatorIndex].currentNode().SetName(locatorName)
            trajectoryIndex = 0
            self.addSequenceRelatedNodesInList(locatorIndex, trajectoryIndex)
            locatorIndexes.append(locatorIndex)
            for index in range(1, numTrajectoryInRow):
              if not locatorName == row[index * self.elementPerLocator]:
                locatorIndex = locatorIndex + 1
                locatorName = row[index * self.elementPerLocator]
                transformNode = slicer.vtkMRMLLinearTransformNode()
                slicer.mrmlScene.AddNode(transformNode)
                self.transformSelector[locatorIndex].setCurrentNode(transformNode)
                self.transformSelector[locatorIndex].currentNode().SetName(locatorName)
                trajectoryIndex = 0
              else:
                trajectoryIndex = trajectoryIndex + 1  
              locatorIndexes.append(locatorIndex)
              self.addSequenceRelatedNodesInList(locatorIndex, trajectoryIndex)
          if rowIndex >= 2:
            # trajectoryIndexInLocator = -1
            for trajectoryIndex in range(numTrajectoryInRow):
              timeStamp = row[trajectoryIndex * self.elementPerLocator]
              # trajectoryIndexInLocator = (trajectoryIndexInLocator + 1) if locatorIndex == locatorIndexes[trajectoryIndex] else 0
              locatorIndex = locatorIndexes[trajectoryIndex]
              if (not timeStamp == " ") and (not timeStamp == ""):
                pos = [float(row[trajectoryIndex * self.elementPerLocator + 1]),
                       float(row[trajectoryIndex * self.elementPerLocator + 2]),
                       float(row[trajectoryIndex * self.elementPerLocator + 3])]
                matrix = vtk.vtkMatrix4x4()
                matrix.Identity()
                matrix.SetElement(0, 3, pos[0])
                matrix.SetElement(1, 3, pos[1])
                matrix.SetElement(2, 3, pos[2])
                transformNode = slicer.vtkMRMLLinearTransformNode()
                transformNode.SetMatrixTransformToParent(matrix)
                proxyNodeName = self.transformSelector[locatorIndex].currentNode().GetName()
                transformNode.SetName(proxyNodeName)
                subTrajectoryIndex = int(row[trajectoryIndex * self.elementPerLocator + 4])
                if subTrajectoryIndex >= len(self.sequenceNodesList[locatorIndex]):
                  self.addSequenceRelatedNodesInList(locatorIndex, subTrajectoryIndex)
                seqNode = self.sequenceNodesList[locatorIndex][subTrajectoryIndex]
                seqNode.SetDataNodeAtValue(transformNode, timeStamp)
                seqNode.SetAttribute(self.REL_TRAJECTORYINDEX_SEQ, str(subTrajectoryIndex))
          rowIndex = rowIndex + 1
    else:
      slicer.util.warningDisplay("file doesn't exists!")

  def onSavingSeperateChannel(self):
    """
    Change the layout of the Export/Import section in the GUI
    :return: None
    """
    if self.savingSeperateChannelCheckBox.checked == True:
      self.fileNameEditor.visible = False
      self.exportLayout.addWidget(self.saveButton)
      self.exportImportFormLayout = qt.QFormLayout(self.exportImportCollapsibleButton)
      self.exportImportFormLayout.addRow("Export to directory: ", self.exportLayout)
      self.exportImportFormLayout.addRow("Import Directory: ", self.importLayout)
    else :
      self.fileNameEditor.visible = True
      self.saveFileLayout.addWidget(self.saveButton)
      self.exportImportFormLayout = qt.QFormLayout(self.exportImportCollapsibleButton)
      self.exportImportFormLayout.addRow("Export to directory: ", self.exportLayout)
      self.exportImportFormLayout.addRow("Export File name: ", self.saveFileLayout)
      self.exportImportFormLayout.addRow("Import File name: ", self.importLayout)

  def saveFile(self):
    """
    Export the tracked data
    :return: None
    """
    if self.savingSeperateChannelCheckBox.checked == False:
      self.saveInOneFile()
    else:
      self.saveInDifferentFiles()
    pass

  def appendValidPos(self, seqNode, posIndex, poses, removeRedundance = True):
    """
    Append valid pos from the sequence node to the list 'poses' if the pos specified by 'row' in the sequence node is not the same as previous pos
    :param seqNode: Sequence node where the poses are stored.
    :param posIndex: index of the position in the sequence node
    :param poses: to which the valid position will append
    :param removeRedundance: flag indicate if redundancy should be moved or not.
    :return: Return True if the evaluated pos at the specified index is valid and added to the poses
    """
    posValid = True
    transformNode = seqNode.GetNthDataNode(posIndex)
    transMatrix = transformNode.GetMatrixTransformToParent()
    pos = [transMatrix.GetElement(0, 3), transMatrix.GetElement(1, 3), transMatrix.GetElement(2, 3)]
    timeStamp = float(seqNode.GetNthIndexValue(posIndex))
    if removeRedundance:
      if posIndex > 0:
        transformNode_pre = seqNode.GetNthDataNode(posIndex - 1)
        transMatrix_pre = transformNode_pre.GetMatrixTransformToParent()
        pos_pre = [transMatrix_pre.GetElement(0, 3), transMatrix_pre.GetElement(1, 3),
                   transMatrix_pre.GetElement(2, 3)]
        if numpy.linalg.norm(numpy.array(pos) - numpy.array(pos_pre)) < 1e-8:
          posValid = False
        else:
          posValid = True
    if posValid:
      poses.append(timeStamp)
      poses.append(pos[0])
      poses.append(pos[1])
      poses.append(pos[2])
      poses.append(seqNode.GetAttribute(self.REL_TRAJECTORYINDEX_SEQ))
      poses.append(" ")
      return True
    return False

  def saveInDifferentFiles(self):
    """
    Save the tracked data from the different locator to different files, one file for each locator.
    Also all the tracjectories are concatenated in to the same columns. Data structure in each file:
    Tracker1
    TimeStamp	X	Y	Z	TrajectoryIndex
    xx        x x x 0
    xx        x x x 0
    xx        x x x 1
    xx        x x x 1
    :return:None
    """
    if os.path.exists(self.exportDirString):
      for i in range(len(self.locatorNodeList)):
        if self.locatorNodeList[i] and (not self.sequenceNodesList[i] == []):
          locatorName = self.locatorNodeList[i].GetName()
          fileName = os.path.join(self.exportDirString, locatorName)
          with open(fileName, 'wb') as csvfile:
            fileWriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            header = []
            title = []
            header.append(self.locatorNodeList[i].GetName())
            header.append(" ")
            header.append(" ")
            header.append(" ")
            header.append(" ")
            header.append(" ")
            title.append("TimeStamp")
            title.append("X")
            title.append("Y")
            title.append("Z")
            title.append("TrajectoryIndex")
            title.append(" ")
            fileWriter.writerow(header)
            fileWriter.writerow(title)
            for j in range(len(self.sequenceNodesList[i])):
              seqNode = self.sequenceNodesList[i][j]
              for row in range(seqNode.GetNumberOfDataNodes()):
                seqNode = self.sequenceNodesList[i][j]
                poses = []
                if self.appendValidPos(seqNode, row, poses, self.removeDuplicatePosCheckBox.checked):
                  fileWriter.writerow(poses)
    else:
      slicer.util.warningDisplay("Path doesn't exists!")

  def saveInOneFile(self):
    """
    Save the tracked data from the different locator to different files, one file for each locator.
    Also all the tracjectories are concatenated in to the same columns. Data structure in each file:
    Tracker1  sequence1               Tracker1 sequence2                Tracker2 sequence1
    TimeStamp	X	Y	Z	TrajectoryIndex   TimeStamp	X	Y	Z	TrajectoryIndex   TimeStamp	X	Y	Z	TrajectoryIndex
    xx        x x x 0                 xx        x x x 1                 xx        x x x 0
    xx        x x x 0                 xx        x x x 1                 xx        x x x 0
    :return:None
    """
    if os.path.exists(self.exportDirString):
      fileName = os.path.join(self.exportDirString, self.fileNameEditor.text)
      with open(fileName, 'wb') as csvfile:
        fileWriter = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        header = []
        title = []
        validLocatorIndex = []
        for i in range(self.nLocators):
          if not self.sequenceNodesList[i] == []:
            validLocatorIndex.append(i)
            for j in range(len(self.sequenceNodesList[i])):
              seqNode = self.sequenceNodesList[i][j]
              if seqNode.GetNumberOfDataNodes() and self.locatorNodeList[i]:
                header.append(self.locatorNodeList[i].GetName())
                header.append(seqNode.GetName())
                header.append(" ")
                header.append(" ")
                header.append(" ")
                header.append(" ")
                title.append("TimeStamp")
                title.append("X")
                title.append("Y")
                title.append("Z")
                title.append("TrajectoryIndex")
                title.append(" ")
        fileWriter.writerow(header)
        fileWriter.writerow(title)
        maxRowNum = 0
        rowIndexes = []
        for i in validLocatorIndex:
          number = []
          if not self.sequenceNodesList[i] == []:
            for j in range(len(self.sequenceNodesList[i])):
              seqNode = self.sequenceNodesList[i][j]
              if seqNode.GetNumberOfDataNodes()> maxRowNum:
                maxRowNum = seqNode.GetNumberOfDataNodes()
              number.append(0)
            rowIndexes.append(number)
        for row in range(maxRowNum):
          poses = []
          for i in validLocatorIndex:
            if not self.sequenceNodesList[i] == []:
              for j in range(len(self.sequenceNodesList[i])):
                seqNode = self.sequenceNodesList[i][j]
                if rowIndexes[i][j] < seqNode.GetNumberOfDataNodes():
                  while True:
                    if self.appendValidPos(seqNode, rowIndexes[i][j], poses, self.removeDuplicatePosCheckBox.checked):
                      break
                    rowIndexes[i][j] = rowIndexes[i][j] + 1
                    if rowIndexes[i][j] >= seqNode.GetNumberOfDataNodes():
                      poses.append(" ")
                      poses.append(" ")
                      poses.append(" ")
                      poses.append(" ")
                      poses.append(" ")
                      poses.append(" ")
                      break
                else:
                  poses.append(" ")
                  poses.append(" ")
                  poses.append(" ")
                  poses.append(" ")
                  poses.append(" ")
                  poses.append(" ")
                rowIndexes[i][j] = rowIndexes[i][j] + 1
          fileWriter.writerow(poses)
    else:
      slicer.util.warningDisplay("Path doesn't exists!")

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def StartCaseImportCallback(self, caller, eventId, callData):
    """
    When the user imports the data from MRMLScene file, the current Slicer mrmlscene will be cleared
    :param caller: mrmlScene
    :param eventId: slicer.vtkMRMLScene.StartImportEvent
    :param callData: None
    :return: none
    """
    print("loading study")
    self.cleanup()


  @vtk.calldata_type(vtk.VTK_OBJECT)
  def LoadCaseCompletedCallback(self, caller, eventId, callData):
    """
    After the data import, initialize the variables in the widget from the imported data.
    :param caller:  mrmlScene
    :param eventId: slicer.vtkMRMLScene.EndImportEvent
    :param callData: None
    :return:
    """
    print("study loaded")
    sequenceNodesList = [[],[],[],[],[]]
    sequenceBrowserNodesList = [[],[],[],[],[]]
    sequenceBrowserNodesCollection = slicer.mrmlScene.GetNodesByClass("vtkMRMLSequenceBrowserNode")
    for index in range(sequenceBrowserNodesCollection.GetNumberOfItems()):
      sequenceBrowserNode = sequenceBrowserNodesCollection.GetItemAsObject(index)
      sequenceNodeID = sequenceBrowserNode.GetAttribute(self.REL_SEQNODE)
      if slicer.mrmlScene.GetNodeByID(sequenceNodeID):
        seqNode = slicer.mrmlScene.GetNodeByID(sequenceNodeID)
        locatorIndex = int(seqNode.GetAttribute(self.REL_LOCATORINDEX_SEQ)[-1])
        sequenceNodesList[locatorIndex].append(seqNode)
        sequenceBrowserNodesList[locatorIndex].append(sequenceBrowserNode)
    # We clear all the markups and model from the loaded mrmlScene to reduce complexity.
    # The markups and model for curve maker will be generated in the self.initialization function.
    markupsNodesCollection = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsFiducialNode")
    modelNodesCollection = slicer.mrmlScene.GetNodesByClass("vtkMRMLModelNode")
    for index in range(markupsNodesCollection.GetNumberOfItems()):
      markupsNode = markupsNodesCollection.GetItemAsObject(index)
      slicer.mrmlScene.RemoveNode(markupsNode.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(markupsNode)
    for index in range(modelNodesCollection.GetNumberOfItems()):
      modelNode = modelNodesCollection.GetItemAsObject(index)
      if modelNode.GetAttribute('vtkMRMLModelNode.rel_needleModel') is None:  # we don't delete related locator model
        slicer.mrmlScene.RemoveNode(modelNode.GetDisplayNode())
        slicer.mrmlScene.RemoveNode(modelNode) 
    self.initialize(sequenceNodesList, sequenceBrowserNodesList)
    for i in range(self.nLocators):
      self.transformSelector[i].setCurrentNode(None)

  def enableCurrentLocator(self, activeIndex, active):
    """
    Enable/Disable the visualization of specific locator specified by the activeIndex.
    :param activeIndex: the index of the locator
    :param active: enable or disable the recording
    :return: None
    """
    tnode = self.transformSelector[activeIndex].currentNode()
    if tnode:
      self.transformSelector[activeIndex].setEnabled(not active)
      self.logic.addLocator(tnode, self.colors[activeIndex])
      mnodeID = tnode.GetAttribute('Locator')
      if mnodeID != None:
        if active:
          locatorNode = slicer.mrmlScene.GetNodeByID(mnodeID)
          locatorNode.SetDisplayVisibility(True)
        else:
          locatorNode = slicer.mrmlScene.GetNodeByID(mnodeID)
          locatorNode.SetDisplayVisibility(False)
          locatorNode.RemoveNodeReferenceIDs("transform")
    else:
      self.locatorRecordCheckBox[activeIndex].setChecked(False)

  def onProcessVarianceChanged(self, value):
    self.processVariance = self.processVarianceSpinBox.value

  def onMeasurementVarianceChanged(self, value):
    self.measurementVariance = self.measurementVarianceSpinBox.value

  def  onMovementThresholdChanged(self, value):
    self.movementThreshold = self.movementThresholdSpinBox.value

  def onDownSampleStepSizeChanged(self, value):
    self.downSampleStepSize = self.downSampleStepSizeSpinBox.value
    
  def onTrajectoyIndexChanged(self, spinbox, value):
    """
    Response to the spinbox value change. new sequence nodes and sequence browser nodes will be created if the spinbox value is larger than the number of available sequence nodes.
    The tracked data of the specific locator will be recorded
    :param spinbox: The spinbox that triggers the signal.
    :param value: value in the spinbox
    :return:
    """
    channelIndex = 0
    for i in range(self.nLocators):
      if self.trajectoryIndexSpinBox[i] == spinbox:
        channelIndex = i
        break
    locatorIndex = -1
    for i in range(len(self.locatorNodeList)):
      if self.transformSelector[channelIndex].currentNode() == self.locatorNodeList[i]:
        locatorIndex = i    
        break
    numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
    if self.locatorRecordCheckBox[channelIndex].checked == True:
      self.disableSpecificLocatorRecording(locatorIndex)
      if numOfSequenceNode < (value+1):
        while numOfSequenceNode < (value+1):
          self.addSequenceRelatedNodesInList(locatorIndex, numOfSequenceNode)
          numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
      self.enableSpecificTrajectoryRecording(locatorIndex, value)
    if self.locatorReplayCheckBox[channelIndex].checked == True:
      if self.trajectoryIndexSpinBoxLastValue[channelIndex] >=0 and self.trajectoryIndexSpinBoxLastValue[channelIndex] < numOfSequenceNode:
        self.disableSpecificTrajectoryReplay(locatorIndex, self.trajectoryIndexSpinBoxLastValue[channelIndex])
      if self.trajectoryIndexSpinBox[channelIndex].value < numOfSequenceNode:
        self.enableSpecificTrajectoryReplay(locatorIndex, self.trajectoryIndexSpinBox[channelIndex].value)
    self.trajectoryIndexSpinBoxLastValue[channelIndex] = value
    
  def addSequenceRelatedNodesInList(self, locatorIndex, trajectoryIndex, sequenceNode = None, sequenceBrowserNode = None):
    """
    Markups fiducial will be added for storing the filted locator trajectory.
    Model node will be added for visualization of the trajectory.
    :param sequenceNode: Sequence node stores the tracked data
    :param sequenceBrowserNode: Sequence browser node record or replay the tracked data
    :param locatorIndex: The index of the locator that needs to be recorded
    :return: None
    """
    if sequenceNode == None or sequenceBrowserNode == None:
      sequenceNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceNode")
      slicer.mrmlScene.AddNode(sequenceNode)
      sequenceBrowserNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceBrowserNode")
      slicer.mrmlScene.AddNode(sequenceBrowserNode)
    sequenceNode.SetAttribute(self.REL_LOCATORINDEX_SEQ, "Locator " + str(trajectoryIndex))
    sequenceNode.SetAttribute(self.REL_TRAJECTORYINDEX_SEQ, str(trajectoryIndex))
    if not sequenceNode.GetName()[-9:] == ("-Locator " + str(locatorIndex)):
      sequenceNode.SetName(sequenceNode.GetName() + "-Locator " + str(locatorIndex))
    self.sequenceNodesList[locatorIndex].append(sequenceNode)
    self.sequenceBrowserNodesList[locatorIndex].append(sequenceBrowserNode)
    self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex].SetAttribute(self.REL_SEQNODE,
                                                                              self.sequenceNodesList[locatorIndex][
                                                                                trajectoryIndex].GetID())
    self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex])
    self.sequenceNodeComboBox.setCurrentNode(self.sequenceNodesList[locatorIndex][trajectoryIndex])
    self.addSequenceNodeButton.click()
    self.recordingSamplingSetting.setCurrentIndex(0)
    fiducialNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode")
    fiducialNode.SetAttribute(self.REL_LOCATORINDEX_FIDUCIAL, "Locator " + str(locatorIndex))
    self.trajectoryFidicualsList[locatorIndex].append(fiducialNode)
    fiducialNode.SetLocked(True)
    slicer.mrmlScene.AddNode(fiducialNode)
    modelNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelNode")
    modelNode.SetAttribute(self.REL_LOCATORINDEX_MODEL, "Locator " + str(locatorIndex))
    self.trajectoryModelsList[locatorIndex].append(modelNode)
    slicer.mrmlScene.AddNode(modelNode)
    modelNode.CreateDefaultDisplayNodes()
    modelNode.GetDisplayNode().SetOpacity(0.5)
    modelNode.GetDisplayNode().SetColor(self.colors[locatorIndex])
    self.curveManagersList[locatorIndex].append(self.logic.createNeedleTrajBaseOnCurveMaker(""))
    self.curveManagersList[locatorIndex][trajectoryIndex].connectMarkerNode(self.trajectoryFidicualsList[locatorIndex][trajectoryIndex])
    self.curveManagersList[locatorIndex][trajectoryIndex].connectModelNode(self.trajectoryModelsList[locatorIndex][trajectoryIndex])
    self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.enableAutomaticUpdate(1)
    self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.setInterpolationMethod(1)
    # here we add initial point for the kalman filter. As the pCov is set to 1.0, the first tracked point will be added to trajectory.
    self.logic.filteredData[locatorIndex].append(numpy.zeros((0,0,3))) # numpy.insert(self.logic.filteredData[locatorIndex][trajectoryIndex], [0], pos, axis=0)
    self.logic.pCov[locatorIndex].append(1.0)

  def onAddedTransNode(self, addedNode):
    """
    Adding the user added transformation node into the locatorNodeList
    :param addedNode: Added node from GUI interaction
    :return: None
    """
    addedNode.SetAttribute(self.REL_LOCATOR, "True")
    if not self.locatorNodeList == []:
      addedBefore = False
      for i in range(len(self.locatorNodeList)):
        if addedNode == self.locatorNodeList[i]:
          addedBefore = True
          break
      if addedBefore == False:
        self.locatorNodeList.append(addedNode)
    else:
      self.locatorNodeList.append(addedNode)

  def onLocatorRecording(self, checkbox):
    channelIndex = 0
    for i in range(self.nLocators):
      if self.locatorRecordCheckBox[i] == checkbox:
        channelIndex = i
    locatorIndex = -1
    for i in range(len(self.locatorNodeList)):
      if self.transformSelector[channelIndex].currentNode() == self.locatorNodeList[i]:
        locatorIndex = i    
        break    
    trajectoryIndex = self.trajectoryIndexSpinBox[channelIndex].value
    numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
    if (trajectoryIndex + 1) > numOfSequenceNode:
      while numOfSequenceNode < (trajectoryIndex + 1):
        self.addSequenceRelatedNodesInList(locatorIndex, numOfSequenceNode)
        numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
    if trajectoryIndex > -1 and locatorIndex > -1:
      if checkbox.checked == True:
        if self.locatorReplayCheckBox[channelIndex].checked:
          self.locatorReplayCheckBox[channelIndex].click()
        self.enableCurrentLocator(channelIndex, True)
        self.enableSpecificTrajectoryRecording(locatorIndex, trajectoryIndex)
      else:
        self.enableCurrentLocator(channelIndex, False)
        self.disableSpecificLocatorRecording(locatorIndex)

  def enableSpecificTrajectoryRecording(self, locatorIndex, trajectoryIndex):
      trackedNode = self.locatorNodeList[locatorIndex]
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex])
      self.sequenceNodeCellWidget.cellWidget(0, 1).setCurrentNode(trackedNode)
      self.sequenceNodeCellWidget.cellWidget(0, 3).setChecked(True)
      if self.realTimeReconstructCheckBox.checked:
        self.sequenceNodesList[locatorIndex][trajectoryIndex].RemoveObserver(vtk.vtkCommand.ModifiedEvent)
        self.sequenceNodesList[locatorIndex][trajectoryIndex].AddObserver(vtk.vtkCommand.ModifiedEvent, self.realTimeConstructTrajectory)
      self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex].SetRecordingActive(True)
      self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel.SetDisplayVisibility(True)

  def disableSpecificLocatorRecording(self, locatorIndex):
    numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
    for trajectoryIndex in range(numOfSequenceNode):
      self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex].SetRecordingActive(False)
      if self.realTimeReconstructCheckBox.checked:
        self.sequenceNodesList[locatorIndex][trajectoryIndex].RemoveObserver(vtk.vtkCommand.ModifiedEvent)
      self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel.SetDisplayVisibility(False)

  def enableSpecificTrajectoryReplay(self, locatorIndex, trajectoryIndex):
      trackedNode = self.locatorNodeList[locatorIndex]
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex])
      self.sequenceNodeCellWidget.cellWidget(0, 1).setCurrentNode(trackedNode)
      self.sequenceNodeCellWidget.cellWidget(0, 3).setChecked(True)
      self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex].SetPlaybackActive(True)
      self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel.SetDisplayVisibility(True)

  def disableSpecificTrajectoryReplay(self, locatorIndex, trajectoryIndex):
    self.sequenceBrowserNodesList[locatorIndex][trajectoryIndex].SetPlaybackActive(False)
    if self.realTimeReconstructCheckBox.checked:
      self.sequenceNodesList[locatorIndex][trajectoryIndex].RemoveObserver(vtk.vtkCommand.ModifiedEvent)
    self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel.SetDisplayVisibility(False)

  def onLocatorReplay(self, checkbox):
    channelIndex = 0
    for i in range(self.nLocators):
      if self.locatorReplayCheckBox[i] == checkbox:
        channelIndex = i
    locatorIndex = -1
    for i in range(len(self.locatorNodeList)):
      if self.transformSelector[channelIndex].currentNode() == self.locatorNodeList[i]:
        locatorIndex = i    
        break        
    if locatorIndex > -1:
      numOfSequenceNode = len(self.sequenceNodesList[locatorIndex])
      trajectoryIndex = self.trajectoryIndexSpinBox[channelIndex].value
      self.trajectoryIndexSpinBoxLastValue[channelIndex] = trajectoryIndex
      if (self.trajectoryIndexSpinBox[channelIndex].value + 1) <= numOfSequenceNode:
        if checkbox.checked == True:
          if self.locatorRecordCheckBox[channelIndex].checked:
            self.locatorRecordCheckBox[channelIndex].click()
          self.enableCurrentLocator(channelIndex, True)
          self.enableSpecificTrajectoryReplay(locatorIndex, trajectoryIndex)
        else:
          self.enableCurrentLocator(channelIndex, False)
          self.disableSpecificTrajectoryReplay(locatorIndex, trajectoryIndex)

  def onConstructTrajectory(self, button):
    channelIndex = 0
    for i in range(self.nLocators):
      if self.locatorRecontructButton[i] == button:
        channelIndex = i
    self.enableCurrentLocator(channelIndex, True)
    trajectoryIndex = self.trajectoryIndexSpinBox[channelIndex].value
    locatorIndex = -1
    for i in range(len(self.locatorNodeList)):
      if self.transformSelector[channelIndex].currentNode() == self.locatorNodeList[i]:
        locatorIndex = i
        break
    if trajectoryIndex > -1 and locatorIndex > -1:
      self.constructSpecificTrajectory(locatorIndex, trajectoryIndex)
   
  @vtk.calldata_type(vtk.VTK_OBJECT)
  def realTimeConstructTrajectory(self, caller, eventId, callData):
    locatorIndex = 0
    trajectoryIndex = 0
    numOfLocator = len(self.sequenceNodesList)
    for i in range(numOfLocator):
      numOfSequenceNode = len(self.sequenceNodesList[i])
      for j in range(numOfSequenceNode):
        if self.sequenceNodesList[i][j] == caller:
          locatorIndex = i
          trajectoryIndex = j
    self.constructSpecificTrajectoryRealTime(locatorIndex, trajectoryIndex)
   
  def constructSpecificTrajectory(self, locatorIndex, trajectoryIndex):
    posAll = []
    seqNode = self.sequenceNodesList[locatorIndex][trajectoryIndex]
    self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].RemoveAllMarkups()
    for index in range(seqNode.GetNumberOfDataNodes()):
      transformNode = seqNode.GetNthDataNode(index)
      transMatrix = transformNode.GetMatrixTransformToParent()
      pos = [transMatrix.GetElement(0, 3), transMatrix.GetElement(1, 3), transMatrix.GetElement(2, 3)]
      posAll.append(pos)
    if not posAll == []:
      self.logic.filteredData[locatorIndex][trajectoryIndex] = self.logic.kalmanFilteredPoses(posAll, self.processVariance, self.measurementVariance)
      resampledPos = self.logic.resampleData(self.logic.filteredData[locatorIndex][trajectoryIndex], self.movementThreshold, self.downSampleStepSize)
      if len(resampledPos) >=2:
        for pos in resampledPos:
          self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].AddFiducialFromArray(pos)
          self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].SetNthFiducialLabel(index, "")   
        self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.DestinationNode = self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel
        self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.SourceNode = self.curveManagersList[locatorIndex][trajectoryIndex].curveFiducials
        self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.updateCurve()
        self.curveManagersList[locatorIndex][trajectoryIndex].lockLine()
        self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel.SetDisplayVisibility(True)

  def constructSpecificTrajectoryRealTime(self, locatorIndex, trajectoryIndex):
    seqNode = self.sequenceNodesList[locatorIndex][trajectoryIndex]
    transformNode = seqNode.GetNthDataNode(seqNode.GetNumberOfDataNodes()-1)
    transMatrix = transformNode.GetMatrixTransformToParent()
    pos = [transMatrix.GetElement(0, 3), transMatrix.GetElement(1, 3), transMatrix.GetElement(2, 3)]
    if len(self.logic.filteredData[locatorIndex][trajectoryIndex]) == 0:
      self.logic.filteredData[locatorIndex][trajectoryIndex] = numpy.array([pos])
    else:
      filteredPos, pCov = self.logic.kalmanFilteredPosesRealTime(pos, self.logic.filteredData[locatorIndex][trajectoryIndex], self.logic.pCov[locatorIndex][trajectoryIndex], self.processVariance, self.measurementVariance)
      arrayLength = len(self.logic.filteredData[locatorIndex][trajectoryIndex])
      insertedArray = numpy.insert(self.logic.filteredData[locatorIndex][trajectoryIndex], [arrayLength], filteredPos, axis=0)
      self.logic.filteredData[locatorIndex][trajectoryIndex] = insertedArray
      self.logic.pCov[locatorIndex][trajectoryIndex] = pCov
      resampledPos, valid = self.logic.resampleDataRealTime(self.logic.filteredData[locatorIndex][trajectoryIndex], self.movementThreshold, self.downSampleStepSize)
      if valid:
        self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].AddFiducialFromArray(resampledPos)
        fiducialNum = self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].GetNumberOfFiducials()
        self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].SetNthFiducialLabel(fiducialNum-1, "")
        if self.trajectoryFidicualsList[locatorIndex][trajectoryIndex].GetNumberOfFiducials()>1:
          self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.DestinationNode = self.curveManagersList[locatorIndex][trajectoryIndex]._curveModel
          self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.SourceNode = self.curveManagersList[locatorIndex][trajectoryIndex].curveFiducials
          self.curveManagersList[locatorIndex][trajectoryIndex].cmLogic.updateCurve()
          self.curveManagersList[locatorIndex][trajectoryIndex].lockLine()
    
  def onReload(self, moduleName="TrajectoryReconstructor"):
    # Generic reload method for any scripted module.
    # ModuleWizard will subsitute correct default moduleName.
    self.openIGTLinkIFWidget.layout().addWidget(self.connectorCollapsibleButton)  # return the GUI widget to OpenIGTLinkWidget
    globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)


  def updateGUI(self):
    # Enable/disable GUI components based on the state machine
    pass

class CurveManager():
  def __init__(self):
    try:
      import CurveMaker
    except ImportError:
      return slicer.util.warningDisplay(
        "Error: Could not find extension CurveMaker. Open Slicer Extension Manager and install "
        "CurveMaker.", "Missing Extension")
    self.cmLogic = CurveMaker.CurveMakerLogic()
    self.curveFiducials = None
    self._curveModel = None
    self.opacity = 1
    self.tubeRadius = 0.5
    self.curveName = ""
    self.curveModelName = ""
    self.step = 1
    self.tagEventExternal = None
    self.externalHandler = None

    self.sliceID = "vtkMRMLSliceNodeRed"

    # Slice is aligned to the first point (0) or last point (1)
    self.slicePosition = 0

  def clear(self):
    if self._curveModel:
      slicer.mrmlScene.RemoveNode(self._curveModel.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self._curveModel)
    if self.curveFiducials:
      slicer.mrmlScene.RemoveNode(self.curveFiducials.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self.curveFiducials)
    self.curveFiducials = None
    self._curveModel = None

  def connectModelNode(self, mrmlModelNode):
    if self._curveModel:
      slicer.mrmlScene.RemoveNode(self._curveModel.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self._curveModel)
    self._curveModel = mrmlModelNode

  def connectMarkerNode(self, mrmlMarkerNode):
    if self.curveFiducials:
      slicer.mrmlScene.RemoveNode(self.curveFiducials.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self.curveFiducials)
    self.curveFiducials = mrmlMarkerNode

  def setName(self, name):
    self.curveName = name
    self.curveModelName = "%s-Model" % (name)

  def setSliceID(self, name):
    # ID is either "vtkMRMLSliceNodeRed", "vtkMRMLSliceNodeYellow", or "vtkMRMLSliceNodeGreen"
    self.sliceID = name

  def setDefaultSlicePositionToFirstPoint(self):
    self.slicePosition = 0

  def setDefaultSlicePositionToLastPoint(self):
    self.slicePosition = 1

  def setModelColor(self, r, g, b):

    self.cmLogic.ModelColor = [r, g, b]

    # Make slice intersetion visible
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.SetColor([r, g, b])

    if self.curveFiducials:
      dnode = self.curveFiducials.GetMarkupsDisplayNode()
      if dnode:
        dnode.SetSelectedColor([r, g, b])

  def setModelOpacity(self, opacity):
    # Make slice intersetion visible
    self.opacity = opacity
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.opacity(opacity)

  def setManagerTubeRadius(self, radius):
    self.tubeRadius = radius

  def setModifiedEventHandler(self, handler=None):

    self.externalHandler = handler

    if self._curveModel:
      self.tagEventExternal = self._curveModel.AddObserver(vtk.vtkCommand.ModifiedEvent, self.externalHandler)
      return self.tagEventExternal
    else:
      return None

  def resetModifiedEventHandle(self):

    if self._curveModel and self.tagEventExternal:
      self._curveModel.RemoveObserver(self.tagEventExternal)

    self.externalHandler = None
    self.tagEventExternal = None

  def onLineSourceUpdated(self, caller=None, event=None):

    self.cmLogic.updateCurve()

    # Make slice intersetion visible
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.SetSliceIntersectionVisibility(1)

  def startEditLine(self, initPoint=None):

    if self.curveFiducials == None:
      self.curveFiducials = slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode")
      self.curveFiducials.SetName(self.curveName)
      slicer.mrmlScene.AddNode(self.curveFiducials)
      dnode = self.curveFiducials.GetMarkupsDisplayNode()
      if dnode:
        dnode.SetSelectedColor(self.cmLogic.ModelColor)
    if initPoint != None:
      self.curveFiducials.AddFiducial(initPoint[0], initPoint[1], initPoint[2])
      self.moveSliceToLine()

    if self._curveModel == None:
      self._curveModel = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelNode")
      self._curveModel.SetName(self.curveModelName)
      self.setModelOpacity(self.opacity)
      slicer.mrmlScene.AddNode(self._curveModel)
      modelDisplayNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelDisplayNode")
      modelDisplayNode.SetColor(self.cmLogic.ModelColor)
      modelDisplayNode.SetOpacity(self.opacity)
      slicer.mrmlScene.AddNode(modelDisplayNode)
      self._curveModel.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())

    # Set exetrnal handler, if it has not been.
    if self.tagEventExternal == None and self.externalHandler:
      self.tagEventExternal = self._curveModel.AddObserver(vtk.vtkCommand.ModifiedEvent, self.externalHandler)

    self.cmLogic.DestinationNode = self._curveModel
    self.cmLogic.SourceNode = self.curveFiducials
    self.cmLogic.SourceNode.SetAttribute('CurveMaker.CurveModel', self.cmLogic.DestinationNode.GetID())
    self.cmLogic.updateCurve()

    self.cmLogic.CurvePoly = vtk.vtkPolyData()  ## For CurveMaker bug
    self.cmLogic.enableAutomaticUpdate(1)
    self.cmLogic.setInterpolationMethod(1)
    self.cmLogic.setTubeRadius(self.tubeRadius)

    self.tagSourceNode = self.cmLogic.SourceNode.AddObserver('ModifiedEvent', self.onLineSourceUpdated)

  def endEditLine(self):

    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetCurrentInteractionMode(slicer.vtkMRMLInteractionNode.ViewTransform)  ## Turn off

  def clearLine(self):

    if self.curveFiducials:
      self.curveFiducials.RemoveAllMarkups()
      # To trigger the initializaton, when the user clear the trajectory and restart the planning,
      # the last point of the coronal reference line should be added to the trajectory

    self.cmLogic.updateCurve()

    if self._curveModel:
      pdata = self._curveModel.GetPolyData()
      if pdata:
        pdata.Initialize()

  def getLength(self):

    return self.cmLogic.CurveLength

  def getFirstPoint(self, position):

    if self.curveFiducials == None:
      return False
    elif self.curveFiducials.GetNumberOfFiducials() == 0:
      return False
    else:
      self.curveFiducials.GetNthFiducialPosition(0, position)
      return True

  def getLastPoint(self, position):
    if self.curveFiducials == None:
      return False
    else:
      nFiducials = self.curveFiducials.GetNumberOfFiducials()
      if nFiducials == 0:
        return False
      else:
        self.curveFiducials.GetNthFiducialPosition(nFiducials - 1, position)
        return True

  def moveSliceToLine(self):

    viewer = slicer.mrmlScene.GetNodeByID(self.sliceID)

    if viewer == None:
      return

    if self.curveFiducials.GetNumberOfFiducials() == 0:
      return

    if self.slicePosition == 0:
      index = 0
    else:
      index = self.curveFiducials.GetNumberOfFiducials() - 1

    pos = [0.0] * 3
    self.curveFiducials.GetNthFiducialPosition(index, pos)

    if self.sliceID == "vtkMRMLSliceNodeRed":
      viewer.SetOrientationToAxial()
      viewer.SetSliceOffset(pos[2])
    elif self.sliceID == "vtkMRMLSliceNodeYellow":
      viewer.SetOrientationToSagittal()
      viewer.SetSliceOffset(pos[0])
    elif self.sliceID == "vtkMRMLSliceNodeGreen":
      viewer.SetOrientationToCoronal()
      viewer.SetSliceOffset(pos[1])

  def lockLine(self):

    if (self.curveFiducials):
      self.curveFiducials.SetDisplayVisibility(0)

  def unlockLine(self):

    if (self.curveFiducials):
      self.curveFiducials.SetDisplayVisibility(1)


#------------------------------------------------------------
#
# TrajectoryReconstructorLogic
#
class TrajectoryReconstructorLogic(ScriptedLoadableModuleLogic):

  def __init__(self, parent, nLocators):
    ScriptedLoadableModuleLogic.__init__(self, parent)

    self.scene = slicer.mrmlScene
    self.scene.AddObserver(slicer.vtkMRMLScene.NodeRemovedEvent, self.onNodeRemovedEvent)
    self.widget = None

    self.eventTag = {}

    # IGTL Conenctor Node ID
    self.connectorNodeID = ''

    self.count = 0
    self.pCov = [[],[],[],[],[]]
    self.filteredData = [[],[],[],[],[]]
    
  def setWidget(self, widget):
    self.widget = widget


  def addLocator(self, tnode, color = [0.5,0.5,1]):
    if tnode:
      needleModelID = tnode.GetAttribute('Locator')
      if needleModelID == None:
        needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
        needleModel = self.scene.GetNodeByID(needleModelID)
        needleModel.SetAndObserveTransformNodeID(tnode.GetID())  
        needleModel.SetAttribute("vtkMRMLModelNode.rel_needleModel", "True")
        tnode.SetAttribute('Locator', needleModelID)
        displayNode = needleModel.GetDisplayNode()
        displayNode.SetColor(color)
      else:
        needleModel = slicer.mrmlScene.GetNodeByID(needleModelID)
        if needleModel:
          needleModel.SetAndObserveTransformNodeID(tnode.GetID())  
        return

  def removeLocator(self, mnodeID):
    if mnodeID:
      print 'removeLocator(%s)' % mnodeID
      mnode = self.scene.GetNodeByID(mnodeID)
      if mnode:
        print 'removing from the scene'
        dnodeID = mnode.GetDisplayNodeID()
        if dnodeID:
          dnode = self.scene.GetNodeByID(dnodeID)
          if dnode:
            self.scene.RemoveNode(dnode)
        self.scene.RemoveNode(mnode)

  def createNeedleModel(self, node):
    if node and node.GetClassName() == 'vtkMRMLIGTLTrackingDataBundleNode':
      n = node.GetNumberOfTransformNodes()
      for id in range (n):
        tnode = node.GetTransformNode(id)
        if tnode:
          needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
          needleModel = self.scene.GetNodeByID(needleModelID)
          needleModel.SetAndObserveTransformNodeID(tnode.GetID())
          needleModel.InvokeEvent(slicer.vtkMRMLTransformableNode.TransformModifiedEvent)

  def createNeedleTrajBaseOnCurveMaker(self, name):
    curveManager = CurveManager()
    curveManager.setName(name)
    curveManager.setDefaultSlicePositionToFirstPoint()
    curveManager.setModelColor(1.0, 1.0, 0.5)
    return curveManager

  def createNeedleModelNode(self, name):

    locatorModel = self.scene.CreateNodeByClass('vtkMRMLModelNode')
    
    # Cylinder represents the locator stick
    cylinder = vtk.vtkCylinderSource()
    cylinder.SetRadius(1.5)
    cylinder.SetHeight(100)
    cylinder.SetCenter(0, 0, 0)
    cylinder.Update()

    # Rotate cylinder
    tfilter = vtk.vtkTransformPolyDataFilter()
    trans =   vtk.vtkTransform()
    trans.RotateX(90.0)
    trans.Translate(0.0, -50.0, 0.0)
    trans.Update()
    if vtk.VTK_MAJOR_VERSION <= 5:
      tfilter.SetInput(cylinder.GetOutput())
    else:
      tfilter.SetInputConnection(cylinder.GetOutputPort())
    tfilter.SetTransform(trans)
    tfilter.Update()

    # Sphere represents the locator tip
    sphere = vtk.vtkSphereSource()
    sphere.SetRadius(3.0)
    sphere.SetCenter(0, 0, 0)
    sphere.Update()

    apd = vtk.vtkAppendPolyData()

    if vtk.VTK_MAJOR_VERSION <= 5:
      apd.AddInput(sphere.GetOutput())
      apd.AddInput(tfilter.GetOutput())
    else:
      apd.AddInputConnection(sphere.GetOutputPort())
      apd.AddInputConnection(tfilter.GetOutputPort())
    apd.Update()
    
    locatorModel.SetAndObservePolyData(apd.GetOutput());

    self.scene.AddNode(locatorModel)
    locatorModel.SetScene(self.scene)
    locatorModel.SetName(name)
    
    locatorDisp = locatorModel.GetDisplayNodeID()
    if locatorDisp == None:
      locatorDisp = self.scene.CreateNodeByClass('vtkMRMLModelDisplayNode')
      self.scene.AddNode(locatorDisp)
      locatorDisp.SetScene(self.scene)
      locatorModel.SetAndObserveDisplayNodeID(locatorDisp.GetID());
      
    color = [0, 0, 0]
    color[0] = 0.5
    color[1] = 0.5
    color[2] = 1.0
    locatorDisp.SetColor(color)
    
    return locatorModel.GetID()


  def onNodeRemovedEvent(self, caller, event, obj=None):
    delkey = ''
    if obj == None:
      for k in self.eventTag:
        node = self.scene.GetNodeByID(k)
        if node == None:
          delkey = k
          break

    if delkey != '':
      del self.eventTag[delkey]


  def kalmanFilteredPoses(self, posAll, Q = 1e-5, R = 0.02**2):
    #Q = 1e-5  # process variance
    #R = 0.02 ** 2  # estimate of measurement variance, change to see effect
    totalLen = len(posAll)
    # allocate space for arrays
    hatminus = numpy.zeros(totalLen)  # a priori estimate
    filteredData = numpy.zeros((totalLen,3))
    # intial guesses
    for i in range(3):
      filteredData[0][i] = posAll[0][i]
      P_pre = 1.0
      for k in range(1, totalLen):
        # time update
        hatminus[k] = filteredData[k-1][i]
        Pminus = P_pre + Q

        # measurement update
        K = Pminus / (Pminus + R)
        filteredData[k][i] = hatminus[k] + K * (posAll[k][i] - hatminus[k])
        P_pre = (1 - K) * Pminus
    return filteredData

  def kalmanFilteredPosesRealTime(self, pos, filteredDataAll, pCov, Q = 1e-5, R = 0.02**2):
    #Q = 1e-5  # process variance
    #R = 0.02 ** 2  # estimate of measurement variance, change to see effect
    # allocate space for arrays
    #hatminus = numpy.zeros(totalLen)  # a priori estimate
    #Intial guesses
    totalLen = len(filteredDataAll) # current filtered data length
    filteredPos = [0,0,0]
    for i in range(3):

      # time update
      hatminus = filteredDataAll[totalLen-1][i]
      Pminus = pCov + Q
      # measurement update
      K = Pminus / (Pminus + R)
      filteredPos[i] = hatminus + K * (pos[i] - hatminus)
      pCov = (1 - K) * Pminus
    return filteredPos, pCov

  def resampleData(self, data, movementThreshold = 1.0, step = 10):
    dataLen = len(data)
    if dataLen >= step:
      pos_mean = numpy.zeros((int(dataLen/step),3))
      pos_mean[0,:] = numpy.array([numpy.mean(data[0:step,0]), numpy.mean(data[0:step, 1]), numpy.mean(data[0:step, 2])])
      pos_DownSampled = []
      pos_DownSampled.append(pos_mean[0,:])
      for index in range(step, dataLen-step, step):
        pos_mean[index/step] = numpy.array([numpy.mean(data[index:index+step, 0]), numpy.mean(data[index:index+step, 1]), numpy.mean(data[index:index+step, 2])])
        if numpy.linalg.norm(pos_mean[index/step] - pos_mean[index/step-1])>movementThreshold:
          distance = -1e20
          indexMax = 0
          for indexInner in range(step):
            pos1 = numpy.array(data[index+indexInner,:])
            if len(pos_DownSampled) > 1:
              pos2 = pos_DownSampled[-2]
            else:
              pos2 = pos_DownSampled[0]
            if numpy.linalg.norm(pos1-pos2)>distance:
              indexMax = indexInner
              distance = numpy.linalg.norm(pos1-pos2)
          pos_DownSampled.append(data[index+indexMax,:])
      pos_downSampledArray = numpy.zeros((len(pos_DownSampled),3))
      for index in range(len(pos_DownSampled)):
        pos_downSampledArray[index,:] = pos_DownSampled[index]
      return pos_downSampledArray
    return data

  def resampleDataRealTime(self, data, movementThreshold = 1.0, step = 10):
    dataLen = len(data)
    sectionNum = int(dataLen / step)
    pos_downSampledPoint = numpy.zeros((1,3))
    if abs(float(dataLen)/step - int(dataLen/step))< 1e-15 and sectionNum >=2: # we have received another section of data
      pos_mean_pre = numpy.zeros((1,3))
      pos_mean_pre[0,:] = numpy.array([numpy.mean(data[(sectionNum-2)*step:(sectionNum-1)*step,0]), numpy.mean(data[(sectionNum-2)*step:(sectionNum-1)*step, 1]), numpy.mean(data[(sectionNum-2)*step:(sectionNum-1)*step, 2])])
      pos_mean  = numpy.zeros((1,3))
      pos_mean[0,:]  = numpy.array([numpy.mean(data[(sectionNum-1)*step:sectionNum*step, 0]), numpy.mean(data[(sectionNum-1)*step:sectionNum*step, 1]), numpy.mean(data[(sectionNum-1)*step:sectionNum*step, 2])])
      if numpy.linalg.norm(pos_mean - pos_mean_pre)>movementThreshold:
        distance = -1e20
        indexMax = 0
        for indexInner in range(step):
          pos1 = numpy.array(data[(sectionNum-1)*step+indexInner,:])
          if numpy.linalg.norm(pos1-pos_mean_pre)>distance:
            indexMax = indexInner
            distance = numpy.linalg.norm(pos1-pos_mean_pre)
        pos_downSampledPoint = data[(sectionNum-1)*step+indexMax,:]
        return pos_downSampledPoint, True
    return pos_downSampledPoint, False

