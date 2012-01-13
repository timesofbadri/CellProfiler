'''<b>Metadata</b> - Associate metadata with images
<hr>
TO-DO: document module
'''

import re
import os

import cellprofiler.cpmodule as cpm
import cellprofiler.pipeline as cpp
import cellprofiler.settings as cps
from cellprofiler.modules.images import FilePredicate
from cellprofiler.modules.images import ExtensionPredicate
from cellprofiler.modules.images import ImagePredicate
from cellprofiler.modules.images import DirectoryPredicate
from cellprofiler.modules.images import Images, NODE_IMAGE_PLANE

X_AUTOMATIC_EXTRACTION = "Automatic"
X_MANUAL_EXTRACTION = "Manual"
X_IMPORTED_EXTRACTION = "Import metadata"
X_ALL_EXTRACTION_METHODS = [X_AUTOMATIC_EXTRACTION, 
                            X_MANUAL_EXTRACTION,
                            X_IMPORTED_EXTRACTION]
XM_FILE_NAME = "From file name"
XM_FOLDER_NAME = "From folder name"

F_ALL_IMAGES = "All images"
F_FILTERED_IMAGES = "Images selected using a filter"
COL_PATH = "Path / URL"
COL_SERIES = "Series"
COL_INDEX = "Index"
COL_CHANNEL = "Channel"

'''Index of the extraction method count in the settings'''
IDX_EXTRACTION_METHOD_COUNT = 1
'''Index of the first extraction method block in the settings'''
IDX_EXTRACTION_METHOD = 2
'''# of settings in an extraction method block'''
LEN_EXTRACTION_METHOD = 6

class Metadata(cpm.CPModule):
    variable_revision_number = 1
    module_name = "Metadata"
    category = "File Processing"

    def create_settings(self):
        self.pipeline = None
        self.ipds = []
        self.wants_metadata = cps.Binary(
            "Extract metadata?", False,
        doc = "Do your file or path names or file headers contain information\n"
            "(metadata) you would like to extract and store along with your "
            "measurements?")
        
        self.extraction_methods = []
        self.add_extraction_method(False)
        self.extraction_method_count = cps.HiddenCount(
            self.extraction_methods, "Extraction method count")
        self.add_extraction_method_button = cps.DoSomething(
            "Add another extraction method",
            "Add", self.add_extraction_method)
        self.table = cps.Table("")
        self.update_table_button = cps.DoSomething(
            "Update table", "Update", self.update_table)
        
    def add_extraction_method(self, can_remove = False):
        group = cps.SettingsGroup()
        self.extraction_methods.append(group)
        if can_remove:
            group.append("divider", cps.Divider())
            
        group.append("extraction_method", cps.Choice(
            "Extraction method", X_ALL_EXTRACTION_METHODS,
            doc="To do"))
        
        group.append("source", cps.Choice(
            "Source", [XM_FILE_NAME, XM_FOLDER_NAME],
            doc = """Do you want to extract metadata from the image's file
            name or from its folder name?"""))
        
        group.append("file_regexp", cps.RegexpText(
            "Regular expression", 
            '^(?P<Plate>.*)_(?P<Well>[A-P][0-9]{2})_s(?P<Site>[0-9])_w(?P<ChannelNumber>[0-9])',
            get_example_fn = self.example_file_fn,
            doc = """
            <a name='regular_expression'><i>(Used only if you want to extract 
            metadata from the file name)</i><br>
            The regular expression to extract the metadata from the file name 
            is entered here. Note that this field is available whether you have 
            selected <i>Text-Regular expressions</i> to load the files or not.
            Please see the general module help for more information on 
            construction of a regular expression.</a>
            <p>Clicking the magnifying glass icon to the right will bring up a
            tool for checking the accuracy of your regular expression. The 
            regular expression syntax can be used to name different parts of 
            your expression. The syntax <i>(?P&lt;fieldname&gt;expr)</i> will 
            extract whatever matches <i>expr</i> and assign it to the 
            measurement,<i>fieldname</i> for the image.
            <p>For instance, a researcher uses plate names composed of a string 
            of letters and numbers, followed by an underscore, then the well, 
            followed by another underscore, followed by an "s" and a digit
            representing the site taken within the well (e.g., <i>TE12345_A05_s1.tif</i>).
            The following regular expression will capture the plate, well, and 
            site in the fields "Plate", "Well", and "Site":<br><br>
            <table border = "1">
            <tr><td colspan = "2">^(?P&lt;Plate&gt;.*)_(?P&lt;Well&gt;[A-P][0-9]{1,2})_s(?P&lt;Site&gt;[0-9])</td></tr>
            <tr><td>^</td><td>Start only at beginning of the file name</td></tr>
            <tr><td>(?P&lt;Plate&gt;</td><td>Name the captured field <i>Plate</i></td></tr>
            <tr><td>.*</td><td>Capture as many characters as follow</td></tr>
            <tr><td>_</td><td>Discard the underbar separating plate from well</td></tr>
            <tr><td>(?P&lt;Well&gt;</td><td>Name the captured field <i>Well</i></td></tr>
            <tr><td>[A-P]</td><td>Capture exactly one letter between A and P</td></tr>
            <tr><td>[0-9]{1,2}</td><td>Capture one or two digits that follow</td></tr>
            <tr><td>_s</td><td>Discard the underbar followed by <i>s</i> separating well from site</td></tr>
            <tr><td>(?P&lt;Site&gt;</td><td>Name the captured field <i>Site</i></td></tr>
            <tr><td>[0-9]</td><td>Capture one digit following</td></tr>
            </table>
            
            <p>The regular expression can be typed in the upper text box, with 
            a sample file name given in the lower text box. Provided the syntax 
            is correct, the corresponding fields will be highlighted in the same
            color in the two boxes. Press <i>Submit</i> to enter the typed 
            regular expression.</p>
            
            <p>You can create metadata tags for any portion of the filename or path, but if you are
            specifying metadata for multiple images in a single <b>LoadImages</b> module, an image cycle can 
            only have one set of values for each metadata tag. This means that you can only 
            specify the metadata tags which have the same value across all images listed in the module. For example,
            in the example above, you might load two wavelengths of data, one named <i>TE12345_A05_s1_w1.tif</i>
            and the other <i>TE12345_A05_s1_w2.tif</i>, where the number following the <i>w</i> is the wavelength. 
            In this case, a "Wavelength" tag <i>should not</i> be included in the regular expression
            because while the "Plate", "Well" and "Site" metadata is identical for both images, the wavelength metadata is not.</p>
            
            <p>Note that if you use the special fieldnames <i>&lt;WellColumn&gt;</i> and 
            <i>&lt;WellRow&gt;</i> together, LoadImages will automatically create a <i>&lt;Well&gt;</i>
            metadata field by joining the two fieldname values together. For example, 
            if <i>&lt;WellRow&gt;</i> is "A" and <i>&lt;WellColumn&gt;</i> is "01", a field 
            <i>&lt;Well&gt;</i> will be "A01". This is useful if your well row and column names are
            separated from each other in the filename, but you want to retain the standard 
            well nomenclature.</p>"""))
   
        group.append("folder_regexp", cps.RegexpText(
            "Regular expression",
            '(?P<Date>[0-9]{4}_[0-9]{2}_[0-9]{2})$',
            get_example_fn = self.example_directory_fn,
            doc="""
            <i>(Used only if you want to extract metadata from the path)</i><br>
            Enter the regular expression for extracting the metadata from the 
            path. Note that this field is available whether you have selected 
            <i>Text-Regular expressions</i> to load the files or not.
            
            <p>Clicking the magnifying glass icon to the right will bring up a
            tool that will allow you to check the accuracy of your regular 
            expression. The regular expression syntax can be used to 
            name different parts of your expression. The syntax 
            <i>(?&lt;fieldname&gt;expr)</i> will extract whatever matches 
            <i>expr</i> and assign it to the image's <i>fieldname</i> measurement.
                        
            <p>For instance, a researcher uses folder names with the date and 
            subfolders containing the images with the run ID 
            (e.g., <i>./2009_10_02/1234/</i>) The following regular expression 
            will capture the plate, well, and site in the fields 
            <i>Date</i> and <i>Run</i>:<br>
            <table border = "1">
            <tr><td colspan = "2">.*[\\\/](?P&lt;Date&gt;.*)[\\\\/](?P&lt;Run&gt;.*)$</td></tr>
            <tr><td>.*[\\\\/]</td><td>Skip characters at the beginning of the pathname until either a slash (/) or
            backslash (\\) is encountered (depending on the operating system)</td></tr>
            <tr><td>(?P&lt;Date&gt;</td><td>Name the captured field <i>Date</i></td></tr>
            <tr><td>.*</td><td>Capture as many characters that follow</td></tr>
            <tr><td>[\\\\/]</td><td>Discard the slash/backslash character</td></tr>
            <tr><td>(?P&lt;Run&gt;</td><td>Name the captured field <i>Run</i></td></tr>
            <tr><td>.*</td><td>Capture as many characters as follow</td></tr>
            <tr><td>$</td><td>The <i>Run</i> field must be at the end of the path string, i.e., the
            last folder on the path. This also means that the Date field contains the parent
            folder of the Date folder.</td></tr>
            </table></p>"""))
 
        group.append("filter_choice", cps.Choice(
            "Filter images",
            [F_ALL_IMAGES, F_FILTERED_IMAGES],
            doc = """Do you want to extract data from all of the images
            chosen by the <b>Images</b> module or on a subset of the images?"""))
        
        group.append("filter", cps.Filter(
            "", [FilePredicate(),
                 DirectoryPredicate(),
                 ExtensionPredicate(),
                 ImagePredicate()],
            'or (file does contain "")',
            doc = """Pick the files for metadata extraction."""))
                 
        group.can_remove = can_remove
        if can_remove:
            group.append("remover", cps.RemoveSettingButton(
                'Remove above extraction method', 'Remove',
                self.extraction_methods, group))
            
    def settings(self):
        result = [self.wants_metadata, self.extraction_method_count]
        for group in self.extraction_methods:
            result += [
                group.extraction_method, group.source, group.file_regexp,
                group.folder_regexp, group.filter_choice, group.filter]
        return result
    
    def visible_settings(self):
        result = [self.wants_metadata]
        if self.wants_metadata:
            for group in self.extraction_methods:
                if group.can_remove:
                    result += [group.divider]
                result += [group.extraction_method]
                if group.extraction_method == X_MANUAL_EXTRACTION:
                    result += [group.source]
                    if group.source == XM_FILE_NAME:
                        result += [group.file_regexp]
                    elif group.source == XM_FOLDER_NAME:
                        result += [group.folder_regexp]
                    result += [group.filter_choice]
                    if group.filter_choice == F_FILTERED_IMAGES:
                        result += [group.filter]
                if group.can_remove:
                    result += [group.remover]
            result += [self.add_extraction_method_button, self.table,
                       self.update_table_button]
        return result
    
    def example_file_fn(self):
        '''Get an example file name for the regexp editor'''
        if len(self.ipds) > 0:
            return os.path.split(self.ipds[0].path)[1]
        return "PLATE_A01_s1_w11C78E18A-356E-48EC-B204-3F4379DC43AB.tif"
            
    def example_directory_fn(self):
        '''Get an example directory name for the regexp editor'''
        if len(self.ipds) > 0:
            return os.path.split(self.ipds[0].path)[0]
        return "/images/2012_01_12"
        
    def run(self, workspace):
        pass
    
    get_image_plane_details = Images.get_image_plane_details
    
    def get_ipd_metadata(self, ipd):
        '''Get the metadata for an image plane details record'''
        assert isinstance(ipd, cpp.ImagePlaneDetails)
        m = ipd.metadata.copy()
        for group in self.extraction_methods:
            if group.filter_choice == F_FILTERED_IMAGES:
                match = group.filter.evaluate(
                    (NODE_IMAGE_PLANE, 
                     Images.make_modpath_from_ipd(ipd), self))
                if (not match) and match is not None:
                    continue
            if group.extraction_method == X_MANUAL_EXTRACTION:
                m.update(self.manually_extract_metadata(group, ipd))
            elif group.extraction_method == X_AUTOMATIC_EXTRACTION:
                m.update(self.automatically_extract_metadata(group, ipd))
            elif group.extraction_method == X_IMPORTED_EXTRACTION:
                m.update(self.import_metadata(group, ipd))
        return m
                
    def manually_extract_metadata(self, group, ipd):
        if group.source == XM_FILE_NAME:
            text = os.path.split(ipd.path)[1]
            pattern = group.file_regexp.value
        elif group.source == XM_FOLDER_NAME:
            text = os.path.split(ipd.path)[0]
            pattern = group.folder_regexp.value
        else:
            return {}
        match = re.search(pattern, text)
        if match is None:
            return {}
        return match.groupdict()
    
    def automatically_extract_metadata(self, group, ipd):
        return {}
    
    def import_metadata(self, group, ipd):
        return {}
    
    def on_activated(self, pipeline):
        self.pipeline = pipeline
    
        images_modules = [module for module in self.pipeline.modules()
                          if isinstance(module, Images)]
        if (len(images_modules) > 0 and 
            images_modules[0].module_num < self.module_num):
            images_module = images_modules[0]
            ipds = [
                ipd for ipd in pipeline.image_plane_details
                if images_module.filter.evaluate((
                    NODE_IMAGE_PLANE, 
                    images_module.make_modpath_from_ipd(ipd),
                    self)) is not False]
        else:
            ipds = pipeline.image_plane_details
        self.ipds = ipds
        self.update_table()
        
    def update_table(self):
        columns = set()
        for ipd in self.ipds:
            for column in self.get_ipd_metadata(ipd).keys():
                columns.add(column)
        columns = [COL_PATH, COL_SERIES, COL_INDEX, COL_CHANNEL] + \
            sorted(list(columns))
        self.table.clear_columns()
        self.table.clear_rows()
        for i, column in enumerate(columns):
            self.table.insert_column(i, column)
            
        data = []
        for ipd in self.ipds:
            row = [ipd.path, ipd.series, ipd.index, ipd.channel]
            metadata = self.get_ipd_metadata(ipd)
            row += [metadata.get(column) for column in columns[4:]]
            data.append(row)
        self.table.add_rows(columns, data)
        
    def on_deactivated(self):
        self.pipeline = None
        
    def prepare_settings(self, setting_values):
        '''Prepare the module to receive the settings'''
        #
        # Set the number of extraction methods based on the extraction method
        # count.
        #
        n_extraction_methods = int(setting_values[IDX_EXTRACTION_METHOD_COUNT])
        if len(self.extraction_methods) > n_extraction_methods:
            del self.extraction_methods[n_extraction_methods:]
            
        while len(self.extraction_methods) < n_extraction_methods:
            self.add_extraction_method()
        
        
                     