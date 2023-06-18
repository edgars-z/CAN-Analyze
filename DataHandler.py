import numpy as np
import pandas as pd
import json
from fnmatch import fnmatch


class DataHandler():
    def __init__(self, col_names:list[str]):
        """A class used to load and manipulate CAN log data

        Args:
            col_names (list[str]): List of column names that log data will contain
        """
        #A starting list of column names for log data
        self.column_names = col_names
        self.initial_column_count = len(self.column_names)

        #A Numpy array containing loaded and processed CAN data along with trace values
        self.log_data = np.full((1,self.initial_column_count),"")
        self.log_file_loaded = False

        #A list of filters to be applied to the CAN log
        #columns = ["Level", "Filter", "Description", "Subfilter", "Colour"]
        self.filter_list = []
        self.filter_loaded = False

        #A list of dicts containing trace name, high message, low message
        self.traces = []
        self.trace_config_loaded = False

    def load_file(self, filename:str) -> str:
        """Determines whether the file is a CanView log or CanView filter or trace configuration and then loads it appropriately
        Args:
            filename (str): path to file to be loaded

        Returns:
            str: file type that was loaded ["trace_config", "log_file", "filter", ""]
        """        
        self.print_status("Loading %s" % filename)
        file_type = ""
        if fnmatch(filename,"*.json"):
            file_type = "trace_config"
            self.trace_config_loaded = self.load_trace_config(filename)
        else:
            file_header = open(filename, "r").read().splitlines()
            if "HEADER_BEGIN" in file_header[0]:
                file_type = "log_file"
                self.log_file_loaded = self.load_canview_log(filename)
            elif "// CanView Filter" in file_header[1]:
                file_type = "filter"
                self.filter_loaded = self.load_canview_filter(filename)
            else:
                self.print_status("File type not recognized")

        if self.log_file_loaded:
            if self.filter_loaded:
                self.apply_filters()
            if self.trace_config_loaded:
                self.add_trace_points()

        return file_type

    def load_canview_log(self, filename:str):
        """Loads CAN message log in CanView format
        Args:
            filename (str): path to file to be loaded
        """

        file_header = open(filename, "r").read().splitlines()

        #Check if this is a CanView log
        if "HEADER_BEGIN" in file_header[0]:
            #Get the 3rd row of the header which contains column spacing for this file
            col_header = [int(i) for i in file_header[3].split(",")]

            column_spacing = [
                (3, 2+col_header[0]), #Delta time
                (2+col_header[0], 2+col_header[0]+col_header[1]), #Description
                (2+col_header[0]+col_header[1], 2+col_header[0]+col_header[1]+col_header[2]), #Message ID
                (2+col_header[0]+col_header[1]+col_header[2]+0*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+0*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+1*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+1*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+2*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+2*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+3*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+3*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+4*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+4*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+5*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+5*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+6*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+6*col_header[3]+2),
                (2+col_header[0]+col_header[1]+col_header[2]+7*col_header[3], 2+col_header[0]+col_header[1]+col_header[2]+7*col_header[3]+2),
                ]
            column_names = ["Delta", "Description", "ID", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7"]

            #Find end of header
            i = 4
            header_end_found = False
            while not header_end_found:
                if "HEADER_END" in file_header[i]:
                    header_end_found = True
                i = i + 1

            if header_end_found:
                #self.print_status("Header end found on line %d" % i)
                df = pd.read_fwf(filename,colspecs=column_spacing, skiprows=i+1, dtype=str, names=column_names, index_col=False)

                #Remove units from delta time and add a new column with cumulative time
                df["Delta"] = df["Delta"].str.replace("-","0")
                df["Delta"] = df["Delta"].str.replace("ms","").astype("float")
                df.insert(loc=0,column="Time",value=0.0)
                df["Time"] = df["Delta"].cumsum()
                df["Colour"] = ""
                self.log_data = df.replace(np.nan,"").to_numpy()
                self.print_status("CanView log loaded: %d lines" % len(self.log_data))
                return True
        
        self.print_status("Failed to load CanView log")
        return False


    def load_canview_filter(self, filename:str):
        """Loads a filter file which contains definitions and colours to be applied to CAN messages
        Args:
            filename (str): path to file to be loaded
        """
        filter_file = open(filename, "r").read().splitlines()
        #Clear the filter list in case some filters have already been loaded
        self.filter_list = []
        filter_level = 0
        #Iterate through lines in filter file
        for line in filter_file:
            if line[:2] == "//" or line[:2] == "--" or line == "" or len(line)<8:
                #Skip comment lines, dividers or empty lines
                continue
            elif "FILTERS:" in line:
                #Found the start of the main filter list
                filter_level = 1
            elif "SUBFILTERS_" in line:
                #Extract the number of the subfilter between "_" and ":"
                filter_level = int(line.partition("_")[2].partition(":")[0])

            else:
                filter_line = line.replace("\t"," ").split("\"")
                #Remove len from the filter
                filter_line[0] = filter_line[0].replace(" x ","")
                #Remove spaces and replace x with ? wildcard
                filter_line[0] = filter_line[0].replace(" ","")
                filter_line[0] = filter_line[0].replace("x","?")

                if "{s" in filter_line[1]:
                    filter_description = filter_line[1].partition("{s")[0]
                    subfilter_level = int(filter_line[1].partition("{s")[2].partition("}")[0])
                else:
                    filter_description = filter_line[1]
                    subfilter_level = 0


                #Add it to the filter list
                #Level, filter, description, subfilter (if present), colour (if present)
                self.filter_list.append([filter_level, filter_line[0], filter_description, subfilter_level, filter_line[2].strip()])
        self.print_status("CanView filter loaded: %d lines" % len(self.filter_list))
        return True
        

    def load_trace_config(self, filename:str):
        """Loads a JSON file containing names of traces to be plotted as well as messages which toggle "high" or "low" value
        Args:
            filename (str): path to file to be loaded
        """
        with open(filename, "r") as read_file:
            self.traces = json.load(read_file)
        
        #Clean up message definitions by leaving only valid hex characters
        chars_to_remove = 'ghijklmnopqrstuvwxyzGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c'
        table = str.maketrans(dict.fromkeys(chars_to_remove))
        for trace in self.traces:
            trace["high_msg"] = trace["high_msg"].translate(table)
            if "next" in trace["low_msg"].lower():
                trace["low_msg"] = "next"
            else:
                trace["low_msg"] = trace["low_msg"].translate(table)

        self.print_status("Trace configuration loaded: %d traces" % len(self.traces))
        #self.save_trace_config("debug.json")
        return True


    def save_trace_config(self, filename:str):
        """Saves a JSON file containing names of traces to be plotted as well as messages which toggle "high" or "low" value 
        Args:
            filename (str): path to file to be saved
        """
        with open(filename, "w") as write_file:
            json.dump(self.traces, write_file)


    def add_trace_points(self):
        """Checks CAN data for "high" and "low" messages for each traces and adds the correspoding trace values to the log
        """        
        
        #Trim the columns to the initial length to delete any columns that may have been added previously
        self.column_names = self.column_names[:self.initial_column_count]
        self.log_data = self.log_data[:,:self.initial_column_count]
        datalines = len(self.log_data)
        for trace in self.traces:
            #Add each trace to the column name list and add an empty column to the log
            self.column_names.append(trace["name"])
            self.log_data = np.concatenate([self.log_data,np.zeros((datalines,1), dtype=np.int8)],axis=1)
            col_index = self.column_names.index(trace["name"])
            #Go through log row by row and set trace value at each row to 1 if there is a match
            print(trace["name"])
            print(trace["high_msg"])
            for row in range(datalines):
                test_string = self.log_data[row][3:12].sum()[:len(trace["high_msg"])]
                if test_string == trace["high_msg"] and self.log_data[row-1][col_index] == 0:
                    self.log_data[row][col_index] = 1
                    continue
                if trace["low_msg"] == "next":
                    self.log_data[row][col_index] = 0
                    continue
                if test_string == trace["low_msg"]:
                    self.log_data[row][col_index] = 0
                    continue
                self.log_data[row][col_index] = self.log_data[row-1][col_index]


    def apply_filters(self):
        """Checks CAN data for matches with filter. Adds description and colour values to the log data
        """        
        for row in range(len(self.log_data)):
            #Format row into a single string without NaNs
            test_string = self.log_data[row][3:12].sum()
            #Clear any existing description
            self.log_data[row][2] = ""
            filter_level = 1
            while filter_level>0:
                #Create a subfilter at the current level
                sf = [item for item in self.filter_list if item[0]==filter_level]
                #Check each row of the dataframe against filter
                for filter_row in range(len(sf)):
                    filter_string = sf[filter_row][1]
                    match = False
                    for char_index in range(len(test_string)):
                        if filter_string[char_index] == "?":
                            match = True
                            continue
                        elif test_string[char_index] != filter_string[char_index]:
                            match = False
                            break
                        else:
                            match = True

                    if match:
                        #If there is a match append filter description to the dataframe
                        self.log_data[row][2] += sf[filter_row][2]

                        #Also add colour
                        self.log_data[row][12] = sf[filter_row][4]

                        #Set filter level to the next one
                        filter_level = sf[filter_row][3]
                        #Stop checking for further filters at this level
                        break

                    if filter_row == len(sf)-1:
                        #Didn't find a match in the entire filter frame / subfilter frame
                        filter_level = 0

    def set_status_output_destination(self, status_function:callable):
        self.status_output = status_function

    def print_status(self, status_text:str):
        if self.status_output:
            self.status_output(status_text)
        else:
            print(status_text)