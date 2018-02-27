import os
import unittest
import time
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from functools import partial
import CurveMaker
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
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...

    self.logic = TrajectoryReconstructorLogic(None)
    self.logic.setWidget(self)
    self.nLocators = 5
    self.elementPerLocator = 5
    self.dirString = ""
    self.fileString = ""

    self.sequenceBrowserWidget = slicer.modules.sequencebrowser.widgetRepresentation()
    self.browsingWidget = None
    self.playWidget = None
    self.replayButton = None
    self.recordButton = None
    self.synchonizedNodesWidget = None
    self.sequenceNodeComboBox = None
    self.addSequenceNodeButton = None
    self.removeSequenceNodeButton = None
    self.sequenceNodeCellWidget = None
    self.sequenceBrowserSetting = None
    self.recordingSamplingSetting = None
    for child in self.sequenceBrowserWidget.children():
      if child.className() == "ctkCollapsibleButton":
        if child.text == 'Browsing':
          self.browsingWidget = child
          for grandChild in self.browsingWidget.children():
            if grandChild.className() == "qMRMLSequenceBrowserPlayWidget":
              self.playWidget = grandChild
              for grandGrandChild in self.playWidget.children():
                if grandGrandChild.className() == "QPushButton":
                  if grandGrandChild.toolTip == '<p>Play/Pause</p>':
                    self.replayButton = grandGrandChild
                  elif grandGrandChild.toolTip == '<p>Record proxy nodes modifications continuously</p>':
                    self.recordButton = grandGrandChild
        elif child.text == 'Synchronized nodes':
          self.synchonizedNodesWidget = child
          for grandChild in self.synchonizedNodesWidget.children():
            if grandChild.className() == "qMRMLNodeComboBox":
              self.sequenceNodeComboBox = grandChild
            elif grandChild.className() == "QPushButton" and grandChild.toolTip == '<p>Add the selected sequence to the browser.</p>':
              self.addSequenceNodeButton = grandChild
            elif grandChild.className() == "QPushButton" and grandChild.toolTip == '<p>Remove the selected sequence(s) from the browser.</p>':
              self.removeSequenceNodeButton = grandChild
            elif grandChild.className() == "QTableWidget":
              self.sequenceNodeCellWidget = grandChild
        elif child.text == "Advanced":
          self.sequenceBrowserSetting = child
          for grandChild in self.sequenceBrowserSetting.children():
            if grandChild.className() == "QComboBox": # set the recording speed to Maximum
              self.recordingSamplingSetting = grandChild
              break

    if (self.sequenceBrowserWidget is None) or (self.browsingWidget is None) or (self.playWidget is None) or \
       (self.replayButton is None) or (self.recordButton is None) or (self.synchonizedNodesWidget is None) or \
       (self.sequenceNodeComboBox is None) or (self.addSequenceNodeButton is None) or (self.removeSequenceNodeButton is None) or \
       (self.sequenceNodeCellWidget is None) or (self.sequenceBrowserSetting is None) or (self.recordingSamplingSetting is None) :
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
    self.connectorCollapsibleButton = None
    for child in self.openIGTLinkIFWidget.children():
      if child.className() == 'ctkCollapsibleButton':
        if child.text == 'Connectors':
          self.connectorCollapsibleButton = child
    if self.connectorCollapsibleButton is None:
      return slicer.util.warningDisplay(
        "Error: Could not load OpenIGTLink widget. either Extension is missing or the API of OpenIGTLink is changed.")
    else:
      self.layout.addWidget(self.connectorCollapsibleButton)
    #
    # Registration Matrix Selection Area
    #
    self.selectionCollapsibleButton = ctk.ctkCollapsibleButton()
    self.selectionCollapsibleButton.text = "Locator ON/OFF"
    self.layout.addWidget(self.selectionCollapsibleButton)
    self.selectionFormLayout = qt.QFormLayout(self.selectionCollapsibleButton)
    self.realTimeReconstruct = qt.QCheckBox()
    self.realTimeReconstruct.setChecked(False)
    self.selectionFormLayout.addRow("Realtime Reconstruct: ", self.realTimeReconstruct)
    self.transformSelector = []
    self.locatorActiveCheckBox = []
    self.locatorReplayCheckBox = []
    self.locatorRecontructButton = []
    for i in range(self.nLocators):
      self.transformSelector.append(slicer.qMRMLNodeComboBox())
      selector = self.transformSelector[i]
      selector.nodeTypes = ( ("vtkMRMLLinearTransformNode"), "" )
      selector.selectNodeUponCreation = True
      selector.addEnabled = False
      selector.removeEnabled = False
      selector.noneEnabled = False
      selector.showHidden = False
      selector.showChildNodeTypes = False
      selector.setMRMLScene( slicer.mrmlScene )
      selector.setToolTip( "Choose a locator transformation matrix" )

      self.locatorActiveCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorActiveCheckBox[i]
      checkbox.checked = 0
      checkbox.text = ' '
      checkbox.setToolTip("Activate locator")
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorRecording, checkbox))

      transformLayout = qt.QHBoxLayout()
      transformLayout.addWidget(selector)
      transformLayout.addWidget(checkbox)

      self.locatorReplayCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorReplayCheckBox[i]
      checkbox.checked = 0
      checkbox.text = ' '
      checkbox.setToolTip("Replay locator")
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorReplay, checkbox))
      transformLayout.addWidget(checkbox)
      
      self.locatorRecontructButton.append(qt.QPushButton())
      pushbutton = self.locatorRecontructButton[i]
      pushbutton.setCheckable(False)
      pushbutton.text = 'ReConstruct'
      pushbutton.setToolTip("Generate the trajectory based on the tracked needle")
      pushbutton.connect(qt.SIGNAL("clicked()"), partial(self.onConstructTrajectory, pushbutton))
      transformLayout.addWidget(pushbutton)
      
      self.selectionFormLayout.addRow("Locator #%d:" % i, transformLayout)

    self.exportImportCollapsibleButton = ctk.ctkCollapsibleButton()
    self.exportImportCollapsibleButton.text = "Export/Import Results"
    self.layout.addWidget(self.exportImportCollapsibleButton)
    self.exportImportFormLayout = qt.QFormLayout(self.exportImportCollapsibleButton)
    self.outputDirBrowserButton = qt.QPushButton()
    self.fileDialog = qt.QFileDialog()
    self.fileNameEditor = qt.QLineEdit()
    self.saveButton = qt.QPushButton()
    self.saveButton.setText("Save")
    exportLayout = qt.QHBoxLayout()
    exportLayout.addWidget(self.outputDirBrowserButton)
    saveFileLayout = qt.QHBoxLayout()
    saveFileLayout.addWidget(self.fileNameEditor)
    saveFileLayout.addWidget(self.saveButton)
    self.outputDirBrowserButton.clicked.connect(self.selectDirectory)
    self.saveButton.clicked.connect(self.saveFile)

    self.inputFileBrowserButton = qt.QPushButton()
    self.inputFileBrowserButton.setText("Input CSV file name")
    self.loadButton = qt.QPushButton()
    self.loadButton.setText("Load")
    importLayout = qt.QHBoxLayout()
    importLayout.addWidget(self.inputFileBrowserButton)
    importLayout.addWidget(self.loadButton)
    self.inputFileBrowserButton.clicked.connect(self.selectFile)
    self.loadButton.clicked.connect(self.loadFile)

    self.exportImportFormLayout.addRow("Export to directory: ", exportLayout)
    self.exportImportFormLayout.addRow("File name: ", saveFileLayout)
    self.exportImportFormLayout.addRow("Import File: ", importLayout)

    self.initialize()

    #--------------------------------------------------
    # connections
    #
    slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.StartImportEvent, self.StartCaseImportCallback)
    slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndImportEvent, self.LoadCaseCompletedCallback)

    # Add vertical spacer
    self.layout.addStretch(1)

  def initialize(self, sequenceNodesList = None, sequenceBrowserNodesList = None):
    self.trajectoryFidicualsList = []
    self.timeStampsList = []
    self.trajectoryModelsList = []
    self.curveManagersList = []
    self.colors = [[0.3, 0.5, 0.5], [0.2, 0.3, 0.6], [0.1, 0.6, 0.5], [0.5, 0.9, 0.5], [0.0, 0.2, 0.8]]
    for i in range(self.nLocators):
      self.trajectoryFidicualsList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode"))
      slicer.mrmlScene.AddNode(self.trajectoryFidicualsList[i])
      self.timeStampsList.append([])
      self.trajectoryModelsList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelNode"))
      slicer.mrmlScene.AddNode(self.trajectoryModelsList[i])
      self.trajectoryModelsList[i].CreateDefaultDisplayNodes()
      self.trajectoryModelsList[i].GetDisplayNode().SetOpacity(0.5)
      self.trajectoryModelsList[i].GetDisplayNode().SetColor(self.colors[i])
      self.curveManagersList.append(self.logic.createNeedleTrajBaseOnCurveMaker(""))
      self.curveManagersList[i].connectMarkerNode(self.trajectoryFidicualsList[i])
      self.curveManagersList[i].connectModelNode(self.trajectoryModelsList[i])
      self.curveManagersList[i].cmLogic.setTubeRadius(2.50)
      self.curveManagersList[i].cmLogic.enableAutomaticUpdate(1)
      self.curveManagersList[i].cmLogic.setInterpolationMethod(1)
    self.sequenceNodesList = []
    self.sequenceBrowserNodesList = []
    if (sequenceNodesList is None) or (sequenceBrowserNodesList is None):
      for i in range(self.nLocators):
        self.sequenceNodesList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceNode"))
        slicer.mrmlScene.AddNode(self.sequenceNodesList[i])
        self.sequenceBrowserNodesList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceBrowserNode"))
        slicer.mrmlScene.AddNode(self.sequenceBrowserNodesList[i])
        self.sequenceBrowserNodesList[i].SetAttribute(self.REL_SEQNODE, self.sequenceNodesList[i].GetID())
        self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[i])
        self.sequenceNodeComboBox.setCurrentNode(self.sequenceNodesList[i])
        self.addSequenceNodeButton.click()
        self.recordingSamplingSetting.setCurrentIndex(0)
    else:
      self.sequenceNodesList = sequenceNodesList
      self.sequenceBrowserNodesList = sequenceBrowserNodesList
      for i in range(self.nLocators):
        self.onConstructTrajectory(self.locatorRecontructButton[i])
    if self.sequenceBrowserNodesList is not None:
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[0])

  def cleanup(self):
    for i in range(self.nLocators):
      if self.sequenceNodesList and self.sequenceNodesList[i]:
        slicer.mrmlScene.RemoveNode(self.sequenceNodesList[i])
      if self.sequenceBrowserNodesList and self.sequenceBrowserNodesList[i]:
        slicer.mrmlScene.RemoveNode(self.sequenceBrowserNodesList[i])
      if self.trajectoryFidicualsList and self.trajectoryFidicualsList[i]:
        slicer.mrmlScene.RemoveNode(self.trajectoryFidicualsList[i])
      if self.trajectoryModelsList and self.trajectoryModelsList[i]:
        slicer.mrmlScene.RemoveNode(self.trajectoryModelsList[i])
      if self.curveManagersList and self.curveManagersList[i]:
        self.curveManagersList[i].clear()
    del self.trajectoryFidicualsList[:]
    del self.sequenceNodesList[:]
    del self.sequenceBrowserNodesList[:]
    del self.trajectoryModelsList[:]
    del self.curveManagersList[:]
    del self.timeStampsList[:]
    slicer.mrmlScene.Clear(0)
    pass

  def selectDirectory(self):
    self.dirString = self.fileDialog.getExistingDirectory()
    if len(self.dirString)>20:
      self.outputDirBrowserButton.setText(".." + self.dirString[-20:])

  def selectFile(self):
    self.fileString = self.fileDialog.getOpenFileName()
    if len(self.fileString)>20:
      self.inputFileBrowserButton.setText(".." + self.fileString[-20:])


  def loadFile(self):
    if not slicer.util.confirmYesNoDisplay("Current MRMLScene will be clear. Do you want to proceed?"):
      return
    self.cleanup()
    self.initialize()
    if os.path.isfile(self.fileString):
      with open(self.fileString, 'rb') as csvfile:
        fileReader = csv.reader(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        rowIndex = 0
        for row in fileReader:
          numLocator = min(len(row)/self.elementPerLocator, self.nLocators)
          if rowIndex == 0:
            for locatorIndex in range(numLocator):
              transformNode = slicer.vtkMRMLLinearTransformNode()
              slicer.mrmlScene.AddNode(transformNode)
              self.transformSelector[locatorIndex].setCurrentNode(transformNode)
              self.transformSelector[locatorIndex].currentNode().SetName(row[locatorIndex*self.elementPerLocator])
              self.trajectoryFidicualsList[locatorIndex].SetLocked(True)
          if rowIndex >= 2:
            for locatorIndex in range(numLocator):
              timeStamp = row[locatorIndex*self.elementPerLocator]
              if not timeStamp == "":
                pos = [float(row[locatorIndex*self.elementPerLocator+1]), float(row[locatorIndex*self.elementPerLocator+2]), float(row[locatorIndex*self.elementPerLocator+3])]
                matrix = vtk.vtkMatrix4x4()
                matrix.Identity()
                matrix.SetElement(0,3,pos[0])
                matrix.SetElement(1,3,pos[1])
                matrix.SetElement(2,3,pos[2])
                transformNode = slicer.vtkMRMLLinearTransformNode()
                transformNode.SetMatrixTransformToParent(matrix)
                proxyNodeName = self.transformSelector[locatorIndex].currentNode().GetName()
                transformNode.SetName(proxyNodeName)
                self.sequenceNodesList[locatorIndex].SetDataNodeAtValue(transformNode, timeStamp)
                self.trajectoryFidicualsList[locatorIndex].AddFiducialFromArray(pos)
                self.trajectoryFidicualsList[locatorIndex].SetNthFiducialLabel(rowIndex-2, "")
          rowIndex = rowIndex + 1
    else:
      slicer.util.warningDisplay("file doesn't exists!")
    pass

  def saveFile(self):
    if os.path.exists(self.dirString):
      fileName = os.path.join(self.dirString, self.fileNameEditor.text)
      with open(fileName, 'wb') as csvfile:
        fileWriter = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        header = []
        title = []
        validLocatorIndex = []
        for i in range(self.nLocators):
          if self.transformSelector[i].currentNode() is not None:
            if self.trajectoryFidicualsList[i].GetNumberOfFiducials():
              header.append(self.transformSelector[i].currentNode().GetName())
              header.append(" ")
              header.append(" ")
              header.append(" ")
              header.append(" ")
              title.append("TimeStamp")
              title.append("X")
              title.append("Y")
              title.append("Z")
              title.append(" ")
              validLocatorIndex.append(i)
        fileWriter.writerow(header)
        fileWriter.writerow(title)
        maxRowNum = 0
        for index in validLocatorIndex:
          if self.trajectoryFidicualsList[index].GetNumberOfFiducials() > maxRowNum:
            maxRowNum = self.trajectoryFidicualsList[index].GetNumberOfFiducials()
        for row in range(maxRowNum):    
          poses = []
          for index in validLocatorIndex:
            if row < self.trajectoryFidicualsList[index].GetNumberOfFiducials():
              pos = [0,0,0]
              self.trajectoryFidicualsList[index].GetNthFiducialPosition(row, pos)
              poses.append(str(self.timeStampsList[index][row]))
              poses.append(str(pos[0]))
              poses.append(str(pos[1]))
              poses.append(str(pos[2]))
              poses.append(" ")
          fileWriter.writerow(poses)
    else:
      slicer.util.warningDisplay("Path doesn't exists!")
    pass

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def StartCaseImportCallback(self, caller, eventId, callData):
    print("loading study")
    self.cleanup()


  @vtk.calldata_type(vtk.VTK_OBJECT)
  def LoadCaseCompletedCallback(self, caller, eventId, callData):
    print("study loaded")
    sequenceNodesList = []
    sequenceBrowserNodesList = []
    sequenceBrowserNodesCollection = slicer.mrmlScene.GetNodesByClass("vtkMRMLSequenceBrowserNode")
    for index in range(sequenceBrowserNodesCollection.GetNumberOfItems()):
      sequenceBrowserNode = sequenceBrowserNodesCollection.GetItemAsObject(index)
      sequenceNodeID = sequenceBrowserNode.GetAttribute(self.REL_SEQNODE)
      if slicer.mrmlScene.GetNodeByID(sequenceNodeID):
        sequenceBrowserNodesList.append(sequenceBrowserNode)
        sequenceNodesList.append(slicer.mrmlScene.GetNodeByID(sequenceNodeID))
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

  def enableCurrentLocator(self, activeIndex):
    removeList = {}
    for i in range(self.nLocators):
      tnode = self.transformSelector[i].currentNode()
      if self.locatorActiveCheckBox[i].checked == True:
        if tnode:
          self.transformSelector[i].setEnabled(False)
          self.logic.addLocator(tnode, self.colors[i])
          mnodeID = tnode.GetAttribute('Locator')
          removeList[mnodeID] = False
        else:
          self.locatorActiveCheckBox[i].setChecked(False)
          self.transformSelector[i].setEnabled(True)
      else:
        if tnode:
          mnodeID = tnode.GetAttribute('Locator')
          if mnodeID != None and not (mnodeID in removeList):
            removeList[mnodeID] = True
            self.logic.unlinkLocator(tnode)
        self.transformSelector[i].setEnabled(True)

  def onLocatorRecording(self, checkbox):
    activeIndex = 0
    for i in range(self.nLocators):
      if self.locatorActiveCheckBox[i] == checkbox:
        activeIndex = i
    if checkbox.checked == True:
      self.enableCurrentLocator(activeIndex)
      trackedNode = self.transformSelector[activeIndex].currentNode()
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[activeIndex])
      self.sequenceNodeCellWidget.cellWidget(0, 1).setCurrentNode(trackedNode)
      self.sequenceNodeCellWidget.cellWidget(0, 3).setChecked(True)
      if self.realTimeReconstruct.checked:
        self.sequenceNodesList[activeIndex].AddObserver(vtk.vtkCommand.ModifiedEvent, self.realTimeConstructTrajectory)
      self.recordButton.setChecked(True)
    else:
      self.recordButton.setChecked(False)
      if self.realTimeReconstruct.checked:
        self.sequenceNodesList[activeIndex].RemoveObserver(vtk.vtkCommand.ModifiedEvent)    

  def onLocatorReplay(self, checkbox):
    activeIndex = 0
    for i in range(self.nLocators):
      if self.locatorReplayCheckBox[i] == checkbox:
        activeIndex = i
    if checkbox.checked == True:
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[activeIndex])
      self.enableCurrentLocator(activeIndex)
      self.replayButton.setChecked(True)
      self.curveManagersList[activeIndex]._curveModel.SetDisplayVisibility(True)
    else:
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[activeIndex])
      self.replayButton.setChecked(False)
      self.curveManagersList[activeIndex]._curveModel.SetDisplayVisibility(False)

  def onConstructTrajectory(self, button):
    activeIndex = 0
    for i in range(self.nLocators):
      if self.locatorRecontructButton[i] == button:
        activeIndex = i
    self.enableCurrentLocator(activeIndex)
    self.constructSpecificTrajectory(activeIndex)
   
  @vtk.calldata_type(vtk.VTK_OBJECT)
  def realTimeConstructTrajectory(self, caller, eventId, callData):
    activeIndex = 0
    for i in range(self.nLocators):
      if self.sequenceNodesList[i] == caller:
        activeIndex = i
    self.constructSpecificTrajectory(activeIndex)
   
  def constructSpecificTrajectory(self, activeIndex):
    seqNode = self.sequenceNodesList[activeIndex]
    self.trajectoryFidicualsList[activeIndex].RemoveAllMarkups()
    self.timeStampsList[activeIndex] = []
    currentTimeStamps = []
    for index in range(seqNode.GetNumberOfDataNodes()):
      transformNode = seqNode.GetNthDataNode(index)
      transMatrix = transformNode.GetMatrixTransformToParent()
      pos = [transMatrix.GetElement(0, 3), transMatrix.GetElement(1, 3), transMatrix.GetElement(2, 3)]
      currentTimeStamps.append(seqNode.GetNthIndexValue(index))
      self.trajectoryFidicualsList[activeIndex].AddFiducialFromArray(pos)
      self.trajectoryFidicualsList[activeIndex].SetNthFiducialLabel(index, "")
    self.timeStampsList[activeIndex] = currentTimeStamps
    self.curveManagersList[activeIndex].cmLogic.DestinationNode = self.curveManagersList[activeIndex]._curveModel
    self.curveManagersList[activeIndex].cmLogic.SourceNode = self.curveManagersList[activeIndex].curveFiducials
    self.curveManagersList[activeIndex].cmLogic.updateCurve()
    self.curveManagersList[activeIndex].lockLine() 
    
  def onReload(self, moduleName="TrajectoryReconstructor"):
    # Generic reload method for any scripted module.
    # ModuleWizard will subsitute correct default moduleName.
    self.openIGTLinkIFWidget.layout().addWidget(self.connectorCollapsibleButton)  # return the GUI widget to OpenIGTLinkWidget
    self.cleanup()
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
    self.tubeRadius = 1.0
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

  def __init__(self, parent):
    ScriptedLoadableModuleLogic.__init__(self, parent)

    self.scene = slicer.mrmlScene
    self.scene.AddObserver(slicer.vtkMRMLScene.NodeRemovedEvent, self.onNodeRemovedEvent)
    self.widget = None

    self.eventTag = {}

    # IGTL Conenctor Node ID
    self.connectorNodeID = ''

    self.count = 0
    
  def setWidget(self, widget):
    self.widget = widget


  def addLocator(self, tnode, color = [0.5,0.5,1]):
    if tnode:
      if tnode.GetAttribute('Locator') == None:
        needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
        needleModel = self.scene.GetNodeByID(needleModelID)
        needleModel.SetAttribute("vtkMRMLModelNode.rel_needleModel", "True")
        needleModel.SetAndObserveTransformNodeID(tnode.GetID())
        tnode.SetAttribute('Locator', needleModelID)
        displayNode = needleModel.GetDisplayNode()
        displayNode.SetColor(color)
        return


  def unlinkLocator(self, tnode):
    if tnode:
      tnode.RemoveAttribute('Locator')
      tnode.RemoveAttribute('TrajectoryModel')
      tnode.RemoveAttribute('TrajectoryFiducial')

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

  def onNewDeviceEvent(self, caller, event, obj=None):

    cnode = self.scene.GetNodeByID(self.connectorNodeID)
    nInNode = cnode.GetNumberOfIncomingMRMLNodes()
    print nInNode
    for i in range (nInNode):
      node = cnode.GetIncomingMRMLNode(i)
      if not node.GetID() in self.eventTag:
        self.eventTag[node.GetID()] = node.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onIncomingNodeModifiedEvent)
        if node.GetNodeTagName() == 'IGTLTrackingDataSplitter':
          n = node.GetNumberOfTransformNodes()
          for id in range (n):
            tnode = node.GetTransformNode(id)
            if tnode and tnode.GetAttribute('Locator') == None:
              print "No Locator"
              needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
              needleModel = self.scene.GetNodeByID(needleModelID)
              needleModel.SetAndObserveTransformNodeID(tnode.GetID())
              needleModel.InvokeEvent(slicer.vtkMRMLTransformableNode.TransformModifiedEvent)
              tnode.SetAttribute('Locator', needleModelID)

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


