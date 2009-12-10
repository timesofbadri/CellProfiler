"""<b>Apply Threshold</b> sets pixel intensities below or above a certain threshold to zero.
<hr>
ApplyThreshold allows you to produce either a grayscale or binary image
based on a threshold which can be pre-selected or calculated automatically using one of many methods.
"""

__version__="$Revision: 6746 $"

import wx
import matplotlib.cm
import matplotlib.backends.backend_wxagg

from cellprofiler.cpmodule import CPModule
from cellprofiler import cpimage
import cellprofiler.settings as cpsetting
from cellprofiler.gui import cpfigure
from cellprofiler.modules.identify import Identify, O_BACKGROUND, O_ENTROPY
from cellprofiler.modules.identify import O_FOREGROUND, O_THREE_CLASS
from cellprofiler.modules.identify import O_TWO_CLASS, O_WEIGHTED_VARIANCE
from cellprofiler.cpmath.threshold import TM_METHODS, TM_MANUAL, TM_MOG, TM_OTSU
from cellprofiler.cpmath.threshold import TM_PER_OBJECT, TM_BINARY_IMAGE

from cellprofiler.cpmath.cpmorphology import strel_disk
from scipy.ndimage.morphology import binary_dilation

RETAIN = "Retain"
SHIFT = "Shift"
GRAYSCALE = "Grayscale"
BINARY = "Binary (black and white)"

class ApplyThreshold(Identify):

    module_name = "ApplyThreshold"
    variable_revision_number = 3
    category = "Image Processing"

    def create_settings(self):
        threshold_methods = [method for method in TM_METHODS
                             if method != TM_BINARY_IMAGE]
        self.image_name = cpsetting.NameSubscriber("Select the input image",
                                "imagegroup", "None", doc = '''
                                Which image do you want to threshold?''')
        
        self.thresholded_image_name = cpsetting.NameProvider("Name the output image",
                                "imagegroup", "ThreshBlue", doc = '''
                                What do you want to call the thresholded image?''')
        
        self.binary = cpsetting.Choice("Select the output image type", [GRAYSCALE, BINARY], doc = '''
                                What kind of output image would you like to produce?<br>
                                <ul>
                                <li><i>Grayscale:</i> If you choose to produce a grayscale image, the pixels that are retained after some pixels are set to zero or shifted (based on your selections for thresholding options) will have their original 
                                intensity values.</li>
                                <li><i>Binary:</i> If you choose to produce a binary image, the pixels that are retained after some pixels are set to zero (based on your selections for thresholding options) will be white and all other pixels will be black (zeroes).</li>
                                </ul>''')
        # if not binary:
        self.low = cpsetting.Binary("Set pixels below a threshold to zero?", False, doc = '''
                                <i>(Only used if a grayscale image is output)</i><br>
                                Use this setting if you would like to threshold dim pixels.''')
        
        self.high = cpsetting.Binary("Set pixels above a threshold to zero?", False, doc = '''
                                <i>(Only used if the output image is grayscale)</i><br>
                                Use this setting if you would like to threshold bright pixels. This setting is useful if you want
                                to mask out bright regions, such as artifacts that saturate the intensity.''')
        
        # if not binary and self.low:
        self.low_threshold = cpsetting.Float("Enter the low threshold value", 0.0, minval=0, maxval=1, doc = '''
                                <i>(Only used if a grayscale image is ouput and pixels below a given intensity are to be set to zero)</i><br>
                                Set pixels below this value to zero. Use this setting if you do not wish to retain any information 
                                about the dim pixels.''')
        
        self.shift = cpsetting.Binary("Subtract the threshold value from the remaining pixel intensities?", False, doc ='''
                                <i>(Only used if the image is grayscale and pixels below a given intensity are to be set to zero)</i><br>
                                Use this setting if you would like the dim pixels to be shifted in value by the amount of the threshold.''')
        
        # if not binary and self.high:
        self.high_threshold = cpsetting.Float("Enter the high threshold value", 1.0, minval=0, maxval=1, doc = '''
                                <i>(Only used if the output image is grayscale and pixels above a given intensity are to be set to zero)</i><br>
                                Set pixels above this value to zero. Use this setting if you do not wish to retain any 
                                information about the bright pixels.''')
        
        self.dilation = cpsetting.Float("Number of pixels by which to expand the thresholding around those excluded bright pixels",
                                0.0, doc = '''
                                <i>(Only used if the output image is grayscale and pixels above a given intensity are to be set to zero)</i><br>
                                This setting is useful to adjust when you are attempting to exclude bright artifactual objects: you can 
                                first set the threshold to exclude these bright objects, but it may also be desirable to expand the
                                thresholded region around those bright objects by a certain distance so as to avoid a 'halo' effect.''')

        # if binary:
        self.manual_threshold = cpsetting.Float("Set pixels below this value to zero and set pixels at least this value to one",
                                0.5,doc = '''
                                <i>(Only used if the output image is binary)</i><br>
                                Use this setting to create a binary thresholded image, which disregards intensity
                                information for both  bright and dim pixels by setting them equal to one and zero, respectively.''')
        
        self.threshold_method = cpsetting.Choice('''Select the thresholding method''',
                                threshold_methods, doc = '''
                                <i>(Only used if the output image is binary)</i><br>
                                This setting allows you to access the same thresholding 
                                methods used in the <b>Identify</b> modules.  For more help on thresholding, including further explanations of the many optional settings, see the Identify Primary Automatic module.''')
        
        self.threshold_range = cpsetting.FloatRange('Lower and upper bounds on threshold',(0,1),0,1)
        
        self.threshold_correction_factor = cpsetting.Float('Threshold correction factor', 1)
        
        self.object_fraction = cpsetting.CustomChoice('Approximate fraction of image covered by objects?',
                                                      ['0.01','0.1','0.2','0.3','0.4','0.5','0.6','0.7','0.8','0.9','0.99'])
        
        self.enclosing_objects_name = cpsetting.ObjectNameSubscriber("Select the input objects","None")
        
        self.two_class_otsu = cpsetting.Choice('Two-class or three-class thresholding?',
                                               [O_TWO_CLASS, O_THREE_CLASS])
        
        self.use_weighted_variance = cpsetting.Choice('Minimize the weighted variance or the entropy?',
                                                [O_WEIGHTED_VARIANCE, O_ENTROPY])
        
        self.assign_middle_to_foreground = cpsetting.Choice("Assign pixels in the middle intensity class to the foreground or the background?",
                                                      [O_FOREGROUND, O_BACKGROUND])

    def visible_settings(self):
        vv = [self.image_name, self.thresholded_image_name, self.binary]
        if self.binary.value == GRAYSCALE:
            vv.append(self.low)
            if self.low.value:
                vv.extend([self.low_threshold, self.shift])
            vv.append(self.high)
            if self.high.value:
                vv.extend([self.high_threshold, self.dilation])
        else:
            vv.append(self.threshold_method)
            if self.threshold_method == TM_MANUAL:
                vv.append(self.manual_threshold)
            else:
                vv += [self.threshold_range, self.threshold_correction_factor]
                if self.threshold_algorithm == TM_MOG:
                    vv.append(self.object_fraction)
                if self.threshold_algorithm == TM_OTSU:
                    vv += [self.two_class_otsu, self.use_weighted_variance]
                    if self.two_class_otsu == O_THREE_CLASS:
                        vv.append(self.assign_middle_to_foreground)
                if self.threshold_modifier == TM_PER_OBJECT:
                    vv.append(self.enclosing_objects_name)
        return vv
    
    def settings(self):
        """Return all  settings in a consistent order"""
        return [self.image_name, self.thresholded_image_name,
                self.binary, self.low, self.high, self.low_threshold,
                self.shift, self.high_threshold, self.dilation,
                self.threshold_method, self.manual_threshold,
                self.threshold_range, self.threshold_correction_factor,
                self.object_fraction, self.enclosing_objects_name,
                self.two_class_otsu, self.use_weighted_variance,
                self.assign_middle_to_foreground]
    
    def upgrade_settings(self, setting_values,
                         variable_revision_number, module_name,
                         from_matlab):
        if from_matlab and variable_revision_number < 4:
            raise NotImplementedError, ("TODO: Handle Matlab CP pipelines for "
                                        "ApplyThreshold with revision < 4")
        if from_matlab and variable_revision_number == 4:
            setting_values = [ setting_values[0],  # ImageName
                                setting_values[1],  # ThresholdedImageName
                                None,
                                None,
                                None,
                                setting_values[2],  # LowThreshold
                                setting_values[3],  # Shift
                                setting_values[4],  # HighThreshold
                                setting_values[5],  # DilationValue
                                TM_MANUAL,          # Manual thresholding
                                setting_values[6],  # BinaryChoice
                                "0,1",              # Threshold range
                                "1",                # Threshold correction factor
                                ".2",               # Object fraction
                                "None"              # Enclosing objects name
                                ]
            setting_values[2] = (BINARY if float(setting_values[10]) > 0
                                 else GRAYSCALE) # binary flag
            setting_values[3] = (cpsetting.YES if float(setting_values[5]) > 0
                                 else cpsetting.NO) # low threshold set
            setting_values[4] = (cpsetting.YES if float(setting_values[7]) > 0
                                 else cpsetting.NO) # high threshold set
            variable_revision_number = 2
            from_matlab = False
        if (not from_matlab) and variable_revision_number == 1:
            setting_values = (setting_values[:9] + 
                              [TM_MANUAL, setting_values[9], "O,1", "1",
                               ".2","None"])
            variable_revision_number = 2
        if (not from_matlab) and variable_revision_number == 2:
            # Added Otsu options
            setting_values = list(setting_values)
            setting_values += [O_TWO_CLASS, O_WEIGHTED_VARIANCE,
                               O_FOREGROUND]
            variable_revision_number = 3
            
        return setting_values, variable_revision_number, from_matlab
        
    def run(self,workspace):
        """Run the module
        
        workspace    - the workspace contains:
            pipeline     - instance of CellProfiler.Pipeline for this run
            image_set    - the images in the image set being processed
            object_set   - the objects (labeled masks) in this image set
            measurements - the measurements for this run
            frame        - display within this frame (or None to not display)
        """
        input = workspace.image_set.get_image(self.image_name,
                                              must_be_grayscale=True)
        pixels = input.pixel_data.copy()
        if self.binary != 'Grayscale':
            if self.threshold_modifier == TM_PER_OBJECT:
                objects = workspace.object_set.get_objects(self.enclosing_objects_name.value)
                labels = objects.segmented
            else:
                labels = None
            local_thresh,ignore = self.get_threshold(pixels,input.mask,labels)
            pixels = (pixels > local_thresh) & input.mask
        else:
            if self.low.value:
                thresholded_pixels = pixels < self.low_threshold.value
                pixels[input.mask & thresholded_pixels] = 0
                if self.shift.value:
                    pixels[input.mask & ~ thresholded_pixels] -= self.low_threshold.value
            if self.high.value:
                undilated = input.mask & (pixels >= self.high_threshold.value)
                dilated = binary_dilation(undilated, strel_disk(self.dilation.value), mask=input.mask)
                pixels[dilated] = 0
        output = cpimage.Image(pixels, parent_image=input)
        workspace.image_set.add(self.thresholded_image_name, output)
        if workspace.display:
            figure = workspace.create_or_find_figure(subplots=(1,2))

            left = figure.subplot(0,0)
            left.clear()
            left.imshow(input.pixel_data,matplotlib.cm.Greys_r)
            left.set_title("Original image: %s"%(self.image_name,))

            right = figure.subplot(0,1)
            right.clear()
            right.imshow(output.pixel_data,matplotlib.cm.Greys_r)
            right.set_title("Thresholded image: %s"%(self.thresholded_image_name,))
