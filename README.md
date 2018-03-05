
### Overview
TrajectoryReconstruct is a [3D Slicer](http://slicer.org) Module for MR tracking and trajectory reconstruction.
![](Screenshots/Animation.gif)
### Usage:
1. Install the dependent [SlicerOpenIGTLink](https://github.com/openigtlink/SlicerOpenIGTLink), [Sequence](https://github.com/SlicerRt/Sequences) and [CurveMaker](https://github.com/tokjun/CurveMaker) extensions. 

2. After install the extensions, the user need to switch to the module `TrajectoryReconstruct`.

3. Setup the communication with the tracking data client using OpenIGTLinkIF panel, please refer to [SlicerOpenIGTLink](https://github.com/openigtlink/SlicerOpenIGTLink) for more information.

4. In the algorithm setting section. Kalman filter is used in the noise deduction, the user needs to set the parameters according to the measurement error and noise level. Two resampling parameters - MovementThreshold and ResampleWindowSize - can also be set here, if the mean position of points in the resampling window has a   movement larger than the threshold value, the point in this section with the largest movement Will be added to the downsampled points.  Also real-time trajectory reconstruc is possible by toggling the 'Real-time Reconstruct' checkbox.
![Alt text](Screenshots/AlgorithmSettings.png?raw=true "Export/Import")

5. Selector the locator to be tracked in the 'Locator' drop down selector.

6. Toggle the 'Record' checkbox, the transformation matrix of locator will be recorded and a tool representing the locator will be shown in the 3D view. Once the recording is finished, untoggle the 'Record' checkbox. 

7. Toggle the 'Replay' checkbox will replay the recorded tracking data. Make sure disconnect the communication with the tracking data client before toggling the replay checkbox, as the replay feature uses the same transformation node as the tracking data from client.

8. Export/Import using Slicer mrmlScene. Just save all the nodes and the mrmlScene in the same folder. Use the saved mrmlScene for importing.

9. Export/Import using csv file.    
![Alt text](Screenshots/Export-Import.png?raw=true "Export/Import")

### Disclaimer

TrajectoryReconstructor, same as 3D Slicer, is a research software. **TrajectoryReconstructor is NOT an FDA-approved medical device**. It is not intended for clinical use. The user assumes full responsibility to comply with the appropriate regulations.  

### Support

Please feel free to contact us for questions, feedback, suggestions, bugs, or you can create issues in the issue tracker: https://github.com/leochan2009/TrajectoryReconstructor/issues

* [Longquan Chen](https://github.com/leochan2009) lchen@bwh.harvard.edu

* [Junichi Tokuda](https://github.com/tokjun) tokuda@bwh.harvard.edu


### Acknowledgments

Development of TrajectoryRecontruct is supported in part by the following NIH grants: 
* R01 EB020667 OpenIGTLink: a network communication interface for closed-loop image-guided interventions
* P41 EB015898 National Center for Image Guided Therapy (NCIGT), http://ncigt.org

















