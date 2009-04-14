'''exporttoexcel.py - export measurements to a CSV file

CellProfiler is distributed under the GNU General Public License.
See the accompanying file LICENSE for details.

Developed by the Broad Institute
Copyright 2003-2009

Please see the AUTHORS file for credits.

Website: http://www.cellprofiler.org
'''

__version__="$Revision$"

import csv
import numpy as np
import os
import uuid
import wx

import cellprofiler.cpmodule as cpm
import cellprofiler.measurements as cpmeas
import cellprofiler.settings as cps
from cellprofiler.measurements import IMAGE, EXPERIMENT
from cellprofiler.preferences import get_absolute_path, get_output_file_name

DELIMITER_TAB = "Tab"
DELIMITER_COMMA = 'Comma (",")'
DELIMITERS = (DELIMITER_TAB, DELIMITER_COMMA)

"""The object group key field - holds key for lookup as list expands/contracts"""
OG_KEY = "Key"

"""The object group's object name field - which object to output"""
OG_OBJECT_NAME = "ObjectName"

"""The checkbox that lets you pick the previous file as your output file"""
OG_PREVIOUS_FILE = "PreviousFile"

"""The file name field of the object group - file name for the data"""
OG_FILE_NAME = "FileName"

"""The remove button field"""
OG_REMOVE_BUTTON = "RemoveButton"

"""Offset of the first object group in the settings"""
SETTING_OG_OFFSET = 6

"""Offset of the object name setting within an object group"""
SETTING_OBJECT_NAME_IDX = 0

"""Offset of the previous file flag setting within an object group"""
SETTING_PREVIOUS_FILE_IDX = 1

"""Offset of the file name setting within an object group"""
SETTING_FILE_NAME_IDX = 2

"""# of settings within an object group"""
SETTING_OBJECT_GROUP_CT = 3

"""The caption for the image set index"""
IMAGE_NUMBER = "ImageNumber"

"""The caption for the object # within an image set"""
OBJECT_NUMBER = "ObjectNumber"

class ExportToExcel(cpm.CPModule):
    '''Exports measurements into a tab-delimited text file which can be
opened in Excel or other spreadsheets
***********************************************************************

This module will convert the measurements to a tab-delimited form and
either combine measurements from separate objects into one table or
output per-object tables to separate files. In addition, you can save
both image and experiment measurements.

Settings:

What delimiter do you want to use?
This is the character that separates columns in the file. Your choices
are comma (","), tab or you can type in your own choice of delimiter.

What data do you want to export?
This is a list of all of the possible data sources which include
experiment-wide data, per-image measurements and per-object measurements.

Do you want to combine the measurements with this object with those of
the previous object?
This checkbox appears if you pick a data source that is an object and the
data source above it (if there is one) is also an object. If you check the
checkbox, ExportToExcel will create a table that concatenates the columns of
measurements for the previous object with the measurements of the following
object. You can use this if there is a one-to-one relationship between the
two objects, for instance if the second objects were created from the first
using IdentifySecondary, to create a table which has cells or other segmented
objects as the rows and measurements taken from the different compartments
in the columns.

What is the name of the file that will hold the data?
ExportToExcel will store the data in a file with this name. You can use "."
as the first character in the path to store the data in the default output
directory and "&" to store the data in the default image directory.

ExportToExcel has an advanced feature that works in conjunction with
the metadata associated with your image. You can segregate image and object
measurements associated with metadata tags by including those metadata tags
in the file name. The syntax for a tag is "\g<tag-name>" where "tag-name"
is the name of your metadata tag as collected by LoadImages or LoadText.
For instance, to export all data in a well to a single file for an experiment
with metadata of "plate", "well_row" and "well_column", you might use
a file name like: "\g<plate>_\g<well_row>\g<well_column>.csv". If you have
a plate named "XZ29" and a well named "A01", you will then get a file
named, "XZ29_A01.csv".
'''

    category = 'File Processing'
    variable_revision_number = 1
    
    def create_settings(self):
        self.module_name = 'ExportToExcel'
        self.delimiter = cps.CustomChoice('What delimiter do you want to use?',
                                          DELIMITERS)
        self.prepend_output_filename = cps.Binary("Do you want to prepend the output file name to the data file names? This can be useful if you want to run a pipeline multiple times without overwriting the old results.", True)
        self.add_metadata = cps.Binary("Do you want to add image metadata columns to your object data?",False)
        self.add_indexes = cps.Binary("Do you want to add an image set number column to your image data and image set number and object number columns to your object data?", False)
        self.excel_limits = cps.Binary("Do you want to limit output to what is allowed in Excel?", False)
        self.pick_columns = cps.Binary("Do you want to pick the columns to output?", False)
        self.object_groups = []
        self.add_object_group()
        self.add_button = cps.DoSomething("Add a new data source.", "Add",
                                           self.add_object_group)
    
    def add_object_group(self):
        key = uuid.uuid4()
        d = {
             OG_KEY: key,
             OG_OBJECT_NAME: EEObjectNameSubscriber("What data did you want to export?"),
             OG_PREVIOUS_FILE: cps.Binary("Do you want to combine the measurements with this object with those of the previous object?",
                                          False),
             OG_FILE_NAME: cps.Text("What is the name of the file that will hold the data?","DATA.csv"),
             OG_REMOVE_BUTTON: cps.DoSomething("Remove this data source:", 
                                               "Remove",
                                               self.remove_object_group, key)    
             }
        self.object_groups.append(d)
        
    def remove_object_group(self, key):
        """Remove the object group whose OG_KEY matches key"""
        index = [x[OG_KEY] for x in self.object_groups].index(key)
        del self.object_groups[index]
        
    def prepare_to_set_values(self, setting_values):
        """Add enough object groups to capture the settings"""
        setting_count = len(setting_values)
        assert ((setting_count - SETTING_OG_OFFSET) % 
                SETTING_OBJECT_GROUP_CT == 0)  
        group_count = int((setting_count - SETTING_OG_OFFSET) / 
                          SETTING_OBJECT_GROUP_CT)
        while len(self.object_groups) > group_count:
            self.remove_object_group(self.object_groups[-1][OG_KEY])
        
        while len(self.object_groups) < group_count:
            self.add_object_group()

    def backwards_compatibilize(self, setting_values, variable_revision_number,
                                 module_name, from_matlab):
        """Adjust the setting values based on the version that saved them
        
        """
        if variable_revision_number == 1 and from_matlab:
            # Added create subdirectories questeion
            setting_values = list(setting_values)
            setting_values.append(cps.NO)
            variable_revision_number = 2
        if variable_revision_number == 2 and from_matlab:
            wants_subdirectories = (setting_values[8] == cps.YES)
            object_names = [x for x in setting_values[:-1]
                            if x != cps.DO_NOT_USE]
            setting_values = [ DELIMITER_TAB, cps.YES, cps.NO, cps.NO, 
                              cps.NO, cps.NO ]
            for name in object_names:
                setting_values.extend([name, cps.NO, "%s.csv"%(name)])
            variable_revision_number = 1
            from_matlab = False
        return setting_values, variable_revision_number, from_matlab

    def settings(self):
        """Return the settings in the order used when storing """
        result = [self.delimiter, self.prepend_output_filename,
                  self.add_metadata, self.add_indexes,
                  self.excel_limits, self.pick_columns]
        for group in self.object_groups:
            result += [group[OG_OBJECT_NAME], group[OG_PREVIOUS_FILE],
                       group[OG_FILE_NAME]]
        return result

    def visible_settings(self):
        """Return the settings as seen by the user"""
        result = [self.delimiter, self.prepend_output_filename,
                  self.add_metadata, self.add_indexes,
                  self.excel_limits, self.pick_columns]
        previous_group = None
        for group in self.object_groups:
            result += [group[OG_OBJECT_NAME]]
            if is_object_group(group):
                if ((not previous_group is None) and
                    is_object_group(previous_group)):
                    #
                    # Show the previous-group button if there was a previous
                    # group and it was an object group
                    #
                    result += [group[OG_PREVIOUS_FILE]]
                    if not group[OG_PREVIOUS_FILE].value:
                        result += [group[OG_FILE_NAME]]
                else:
                    result += [group[OG_FILE_NAME]]
            else:
                result += [group[OG_FILE_NAME]]
            result += [group[OG_REMOVE_BUTTON]]
            previous_group = group
        result += [ self.add_button ]
        return result
    
    def test_valid(self, pipeline):
        '''Test the module settings to make sure they are internally consistent
        
        '''
        super(ExportToExcel, self).test_valid(pipeline)
        if (len(self.delimiter.value) != 1 and
            not self.delimiter.value in (DELIMITER_TAB, DELIMITER_COMMA)):
            raise cps.ValidationError("The CSV field delimiter must be a single character", self.delimiter)

    @property
    def delimiter_char(self):
        if self.delimiter == DELIMITER_TAB:
            return "\t"
        elif self.delimiter == DELIMITER_COMMA:
            return ","
        else:
            return self.delimiter.value
    
    def run(self, workspace):
        #
        # only run on last cycle
        #
        if (workspace.measurements.image_set_number <
            workspace.image_set_list.count()-1):
            return
        
        object_names = []
        #
        # Loop, collecting names of objects that get included in the same file
        #
        for i in range(len(self.object_groups)):
            group = self.object_groups[i]
            last_in_file = ((i == len(self.object_groups)-1) or
                            (not is_object_group(group)) or
                            (not is_object_group(self.object_groups[i+1])) or
                            (not self.object_groups[i+1][OG_PREVIOUS_FILE].value))
            if len(object_names) == 0:
                filename = group[OG_FILE_NAME].value
            object_names.append(group[OG_OBJECT_NAME].value)
            if last_in_file:
                self.run_objects(object_names, filename, workspace)
                object_names = []

    def run_objects(self, object_names, file_name, workspace):
        """Create a file (or files if there's metadata) based on the object names
        
        object_names - a sequence of object names (or Image or Experiment)
                       which tell us which objects get piled into each file
        file_name - a file name or file name with metadata tags to serve as the
                    output file.
        workspace - get the images from here.
        
        """
        if len(object_names) == 1 and object_names[0] == EXPERIMENT:
            self.make_experiment_file(file_name, workspace)
            return
        
        tags = cpmeas.find_metadata_tokens(file_name)
        metadata_groups = workspace.measurements.group_by_metadata(tags)
        for metadata_group in metadata_groups:
            if len(object_names) == 1 and object_names[0] == IMAGE:
                self.make_image_file(file_name, metadata_group.indexes, 
                                     workspace)
            else:
                self.make_object_file(object_names, file_name, 
                                      metadata_group.indexes, workspace)
    
    def make_full_filename(self, file_name, 
                           workspace = None, image_set_index = None):
        """Convert a file name into an absolute path
        
        We do a few things here:
        * apply metadata from an image set to the file name if an 
          image set is specified
        * change the relative path into an absolute one using the "." and "&"
          convention
        * Create any directories along the path
        """
        if not image_set_index is None:
            file_name = workspace.measurements.apply_metadata(file_name,
                                                              image_set_index)
        file_name = get_absolute_path(file_name)
        path, file = os.path.split(file_name)
        if not os.path.isdir(path):
            os.makedirs(path)
        if self.prepend_output_filename.value:
            file = os.path.splitext(get_output_file_name())[0] + file 
        return os.path.join(path,file)
    
    def make_experiment_file(self, file_name, workspace):
        """Make a file containing the experiment measurements
        
        file_name - create a file with this name
        workspace - the workspace that has the measurements
        """
        file_name = self.make_full_filename(file_name)
        fd = open(file_name,"w")
        try:
            writer = csv.writer(fd,delimiter=self.delimiter_char)
            m = workspace.measurements
            for feature_name in m.get_feature_names(EXPERIMENT):
                writer.writerow((feature_name, 
                                 m.get_all_measurements(EXPERIMENT, 
                                                        feature_name)))
        finally:
            fd.close()
    
    def make_image_file(self, file_name, image_set_indexes, workspace):
        """Make a file containing image measurements
        
        file_name - create a file with this name
        image_set_indexes - indexes of the image sets whose data gets
                            extracted
        workspace - workspace containing the measurements
        """
        file_name = self.make_full_filename(file_name, workspace,
                                            image_set_indexes[0])
        fd = open(file_name,"w")
        try:
            writer = csv.writer(fd,delimiter=self.delimiter_char)
            m = workspace.measurements
            image_features = m.get_feature_names(IMAGE)
            if self.add_indexes.value:
                image_features.insert(0, IMAGE_NUMBER)
            for index in image_set_indexes:
                agg_measurements = m.compute_aggregate_measurements(index)
                if index == image_set_indexes[0]:
                    ordered_agg_names = list(agg_measurements.keys())
                    ordered_agg_names.sort()
                    image_features += ordered_agg_names
                    image_features.sort()
                    image_features = self.user_filter_columns(workspace.frame,
                                                              "Image CSV file columns",
                                                              image_features)
                    if image_features is None:
                        return
                    writer.writerow(image_features)
                row = [ index+1
                       if feature_name == IMAGE_NUMBER
                       else agg_measurements[feature_name]
                       if agg_measurements.has_key(feature_name)
                       else m.get_measurement(IMAGE, feature_name, index)
                       for feature_name in image_features]
                row = [ x if np.isscalar(x) else x[0] for x in row]
                writer.writerow(row)
        finally:
            fd.close()
        
    def make_object_file(self, object_names, file_name, 
                         image_set_indexes, workspace):
        """Make a file containing object measurements
        
        object_names - sequence of names of the objects whose measurements
                       will be included
        file_name - create a file with this name
        image_set_indexes - indexes of the image sets whose data gets
                            extracted
        workspace - workspace containing the measurements
        """
        file_name = self.make_full_filename(file_name, workspace,
                                            image_set_indexes[0])
        fd = open(file_name,"w")
        try:
            writer = csv.writer(fd,delimiter=self.delimiter_char)
            m = workspace.measurements
            features = []
            if self.add_indexes.value:
                features += [(IMAGE, IMAGE_NUMBER),
                             (object_names[0], OBJECT_NUMBER)]
            if self.add_metadata.value:
                mdfeatures = [(IMAGE, name) 
                              for name in m.get_feature_names(IMAGE)
                              if name.startswith("Metadata_")]
                mdfeatures.sort()
                features += mdfeatures
            for object_name in object_names:
                ofeatures = [(object_name, feature_name)
                             for feature_name in m.get_feature_names(object_name)]
                ofeatures.sort()
                features += ofeatures
            features = self.user_filter_columns(workspace.frame,
                                                "Select columns for %s"%(file_name),
                                                ["%s:%s"%x for x in features])
            features = [x.split(':') for x in features]
            #
            # We write the object names in the first row of headers if there are
            # multiple objects. Otherwise, we just write the feature names
            #
            for i in (0,1) if len(object_names) > 1 else (1,):
                writer.writerow([x[i] for x in features])
            for img_index in image_set_indexes:
                object_count =\
                     np.max([m.get_measurement(IMAGE, "Count_%s"%name, img_index)
                             for name in object_names])
                columns = [np.repeat(img_index+1, object_count)
                           if feature_name == IMAGE_NUMBER
                           else np.arange(1,object_count+1) 
                           if feature_name == OBJECT_NUMBER
                           else np.repeat(m.get_measurement(IMAGE, feature_name,
                                                            img_index), 
                                          object_count)
                           if object_name == IMAGE
                           else m.get_measurement(object_name, feature_name, 
                                                  img_index)
                           for object_name, feature_name in features]
                for obj_index in range(object_count):
                    row = [ column[obj_index] if obj_index < column.shape[0] 
                           else np.NAN
                           for column in columns]
                    writer.writerow(row)
        finally:
            fd.close()
    
    def user_filter_columns(self, frame, title, columns):
        """Display a user interface for column selection"""
        if (frame is None or
            (self.pick_columns.value == False and
            (self.excel_limits.value == False or len(columns) < 256))):
            return columns
        
        dlg = wx.Dialog(frame,title = title,
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        dlg.SetSizer(sizer)
        list_box = wx.CheckListBox(dlg, choices=columns)
        list_box.SetChecked(range(len(columns)))
        sizer.Add(list_box,1,wx.EXPAND|wx.ALL,3)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer,0,wx.EXPAND)
        count_text = wx.StaticText(dlg,label="%d columns selected"%len(columns))
        sub_sizer.Add(count_text,0,wx.EXPAND|wx.ALL,3)
        select_all_button = wx.Button(dlg, label="All")
        sub_sizer.Add(select_all_button, 0, wx.ALIGN_LEFT|wx.ALL,3)
        select_none_button = wx.Button(dlg, label="None")
        sub_sizer.Add(select_none_button, 0, wx.ALIGN_LEFT|wx.ALL,3)
        def check_all(event):
            for i in range(len(columns)):
                list_box.Check(i, True)
            recount(event)
        def uncheck_all(event):
            for i in range(len(columns)):
                list_box.Check(i, False)
            recount(event)
        def recount(event):
            count = 0
            for i in range(len(columns)):
                if list_box.IsChecked(i):
                    count += 1
            count_text.Label = "%d columns selected"%(count)
        dlg.Bind(wx.EVT_BUTTON, check_all, select_all_button)
        dlg.Bind(wx.EVT_BUTTON, uncheck_all, select_none_button)
        dlg.Bind(wx.EVT_CHECKLISTBOX, recount, list_box)
        button_sizer = wx.StdDialogButtonSizer()
        button_sizer.AddButton(wx.Button(dlg,wx.ID_OK))
        button_sizer.AddButton(wx.Button(dlg,wx.ID_CANCEL))
        button_sizer.Realize()
        sizer.Add(button_sizer,0,wx.EXPAND|wx.ALL,3)
        if dlg.ShowModal() == wx.ID_OK:
            return [columns[i] for i in range(len(columns))
                    if list_box.IsChecked(i)] 
            
def is_object_group(group):
    """True if the group's object name is not one of the static names"""
    return not group[OG_OBJECT_NAME].value in (IMAGE,EXPERIMENT)
  
class EEObjectNameSubscriber(cps.ObjectNameSubscriber):
    """ExportToExcel needs to prepend "Image" and "Experiment" to the list of objects
    
    """
    def get_choices(self, pipeline):
        choices = [ IMAGE, EXPERIMENT]
        choices += cps.ObjectNameSubscriber.get_choices(self, pipeline)
        return choices

    