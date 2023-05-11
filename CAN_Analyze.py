import sys
import os
import ctypes

import matplotlib
matplotlib.use('QtAgg')

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from fnmatch import fnmatch

import numpy as np
import random

import pandas as pd

import json

version = u"0.1.0"

df = pd.DataFrame()
log_data = np.array([])
column_names = ["Time", "Delta", "Description", "ID", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "Colour"]

#A list of filters to be applied to the XCAN log
#columns = ["Level", "Filter", "Description", "Subfilter", "Colour"]
filter_list = []

#A list of dicts containing trace name, high message, low message
traces = []

def loadFile(filename):
    """
    Determines whether the file is a CanView log or CanView filter or trace configuration and then loads it appropriately
    """
    if fnmatch(filename,"*.json"):
        loadTraceConfig(filename)
    else:    
        file_header = open(filename, "r").read().splitlines()
        if "HEADER_BEGIN" in file_header[0]:
            loadCanViewlog(filename)
        elif "// CanView Filter" in file_header[1]:
            loadCanViewfilter(filename)
        else:
            print("File type not recognized")

def loadCanViewlog(filename):

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
    global df, log_data
    df = pd.read_fwf(filename,colspecs=column_spacing, skiprows=6, dtype=str, names=column_names, index_col=False)

    #Remove units from delta time and add a new column with cumulative time
    df["Delta"] = df["Delta"].str.replace("ms","").astype("float")
    df.insert(loc=0,column="Time",value=0.0)
    df["Time"] = df["Delta"].cumsum()
    df["Colour"] = ""
    log_data = df.replace(np.nan,"").to_numpy()


def loadCanViewfilter(filename):
    global filter_list
    filter_file = open(filename, "r").read().splitlines()

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
            filter_list.append([filter_level, filter_line[0], filter_description, subfilter_level, filter_line[2].strip()])

def loadTraceConfig(filename):
    global traces, column_names, log_data
    with open(filename, "r") as read_file:
        traces = json.load(read_file)
        datalines = len(log_data)
        for trace in traces:
            column_names.append(trace["name"])
            log_data = np.concatenate([log_data,np.zeros((datalines,1), dtype=np.int8)],axis=1)



def saveTraceConfig(filename):
    global traces
    with open(filename, "w") as write_file:
        json.dump(traces, write_file)


def add_trace_points():
    global traces, column_names, log_data
    datalines = len(df.index)
    for trace in traces:
        col_index = column_names.index(trace["name"])
        df[trace["name"]] = [random.randint(0,1) for i in range(datalines)]
        for row in range(len(log_data)):
            test_string = log_data[row][3:12].sum()
            if test_string == trace["high_msg"]:
                log_data[row][col_index] = 1
            elif trace["low_msg"] == "next" or test_string == trace["low_msg"]:
                log_data[row][col_index] = 0
            else:
                log_data[row][col_index] = log_data[row-1][col_index]


def apply_filters():
    global filter_list, log_data
    for row in range(len(log_data)):
        #Format row into a single string without NaNs
        test_string = log_data[row][3:12].sum()
        #Clear any existing description
        log_data[row][2] = ""
        filter_level = 1
        while filter_level>0:
            #Create a subfilter at the current level
            #sf = ff[ff["Level"]==filter_level]
            sf = [item for item in filter_list if item[0]==filter_level]
            #Check each row of the dataframe against filter
            for filter_row in range(len(sf)):
                #filter_string = sf.iat[filter_row,1]
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
                
                #if fnmatch(test_string,filter_string):
                if match:
                    #If there is a match append filter description to the dataframe
                    #df.iat[row,2] += sf.iat[filter_row,2]
                    log_data[row][2] += sf[filter_row][2]

                    #Also add colour
                    log_data[row][12] = sf[filter_row][4]

                    #Set filter level to the next one
                    #filter_level = sf.iat[filter_row,3]
                    filter_level = sf[filter_row][3]
                    #Stop checking for further filters at this level
                    break

                if filter_row == len(sf)-1:
                    #Didn't find a match in the entire filter frame / subfilter frame
                    filter_level = 0




class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data[0]
        self.column_names = data[1]

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            #value = self._data.iloc[index.row(), index.column()]
            value = self._data[index.row(), index.column()]
            #Format time and delta columns with 1 digit
            if index.column() == 0:
                if isinstance(value, float):
                    # Render float to 1 digit
                    return "%.1f" % value    
            if index.column() == 1:
                if isinstance(value, float):
                    # Render float to 1 digit and add +
                    return "+%.1f" % value
            if str(value)=="nan":
                return ""
            return str(value)
        
        #Align timestamps in the first two columns to the right. Align description to the left. Align everything else to the center
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 0 or index.column() == 1:
                return Qt.AlignmentFlag.AlignVCenter + Qt.AlignmentFlag.AlignRight
            elif index.column() == 2:
                return Qt.AlignmentFlag.AlignVCenter + Qt.AlignmentFlag.AlignLeft
            else:
                return Qt.AlignmentFlag.AlignVCenter + Qt.AlignmentFlag.AlignHCenter

        #Highlight rows in colours according to the applied filter
        if role == Qt.ItemDataRole.BackgroundRole:
            value = self._data[index.row()]
            row_colour = value[column_names.index("Colour")]
            if row_colour > "":
                #If a colour value is defined for this row, strip underscores and then check if this colour is valid. If not, redefine.
                row_colour = row_colour.replace("_","")
                if not QtGui.QColor(row_colour).isValid():
                    if row_colour == "LIGHTRED":
                        row_colour = "TOMATO"
                    elif row_colour == "LIGHTPURPLE":
                        row_colour = "MEDIUMPURPLE"
                    elif row_colour == "LIGHTORANGE":
                        row_colour = "KHAKI"
                    else:
                        row_colour = "CYAN"
                return QtGui.QColor(row_colour)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                #return str(self._data.columns[section])
                return self.column_names[section]

            if orientation == Qt.Orientation.Vertical:
                #return str(self._data.index[section]+1)               
                #return list(range(1,len(self._data)+1))[section]
                return section+1


class SnappingCursor:
    """
    A cross-hair cursor that snaps to the data point of a line, which is
    closest to the *x* position of the cursor.

    For simplicity, this assumes that *x* values of the data are sorted.
    """
    def __init__(self, ax, line):
        self.ax = ax
        self.vertical_line = ax.axvline(color='k', lw=0.8, ls='--')
        self.measurement_start_line = ax.axvline(color='red', lw=2, ls='-')
        self.measurement_end_line = ax.axvline(color='red', lw=2, ls='-')
        self.measurement_step = 0
        self.measured_value = 0
        self.x, self.y = line.get_data()
        self._last_index = None
        self.text = ax.text(0.0, 0.0, '', va="center", ha="center")
        self.measured_value_text = ax.text(0.0, 0.0, '', va="center", ha="center")
        
        self.measurement_start_line.set_visible(False)
        self.measurement_end_line.set_visible(False)
        self.measured_value_text.set_visible(False)

    def set_cross_hair_visible(self, visible):
        need_redraw = self.vertical_line.get_visible() != visible
        self.vertical_line.set_visible(visible)
        self.text.set_visible(visible)
        return need_redraw

    def on_mouse_move(self, event):
        if not event.inaxes:
            self._last_index = None
            need_redraw = self.set_cross_hair_visible(False)
            if need_redraw:
                self.ax.figure.canvas.draw()
        else:
            self.set_cross_hair_visible(True)
            x, y = event.xdata, event.ydata

            #find index of the nearest match in the data to snap to            
            index = min(np.searchsorted(self.x, x), len(self.x) - 1)
            if index>0 and (abs(self.x[index] - x) > abs(self.x[index-1] - x)):
                index -=1

            if index == self._last_index:
                return  # still on the same data point, no update needed
            self._last_index = index
            x = self.x[index]
            y = self.y[index]
            # update snapline position
            self.vertical_line.set_xdata([x])
            # show current time and line number in log
            self.text.set_text('t=%1.2f ms\nLine %d' % (x,index+1))
            self.text.set_position((x,0))
            self.ax.figure.canvas.draw()

    @QtCore.pyqtSlot(QtGui.QKeyEvent)
    def on_press(self, event):
        print("keypress detected:")
        if event.key == " ":
            print("spacebar")
            if not event.inaxes:
                #press spacebar outside the graph to clear measurement lines
                self.measurement_start_line.set_visible(False)
                self.measurement_end_line.set_visible(False)
                self.measured_value_text.set_visible(False)
                self.ax.figure.canvas.draw()
                self.measurement_step = 0 
            else:
                if self.measurement_step == 0:
                    #press spacear once to set the first measurement line
                    self.measurement_start_line.set_xdata(self.vertical_line.get_xdata())
                    self.measurement_start_line.set_visible(True)
                    self.ax.figure.canvas.draw()  
                    self.measurement_step += 1

                elif self.measurement_step == 1:
                    #press spacebar twice to set the second measurement line and display measured value
                    self.measurement_end_line.set_xdata(self.vertical_line.get_xdata())
                    self.measurement_end_line.set_visible(True)
                    self.measured_value = self.measurement_end_line.get_xdata()[0] - self.measurement_start_line.get_xdata()[0]
                    self.measured_value_text.set_text('Δ %1.2f ms' % abs(self.measured_value))
                    self.measured_value_text.set_position(((self.measurement_end_line.get_xdata()[0]+self.measurement_start_line.get_xdata()[0])/2,0))
                    self.measured_value_text.set_visible(True)
                    self.ax.figure.canvas.draw()  
                    self.measurement_step += 1
                else:
                    #press spacebar again to clear measurement
                    self.measurement_start_line.set_visible(False)
                    self.measurement_end_line.set_visible(False)
                    self.measured_value_text.set_visible(False)
                    self.ax.figure.canvas.draw()  
                    self.measurement_step = 0
        else:
            print(event.key)

    def on_mouse_click(self, event):
        #print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %   ('double' if event.dblclick else 'single', event.button,           event.x, event.y, event.xdata, event.ydata))
        index = min(np.searchsorted(self.x, event.xdata), len(self.x) - 1)
        #print("Row: ", index)
        w.highlightRow(index)


class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

    @QtCore.pyqtSlot(QtGui.QKeyEvent)
    def onKeyPressEvent(self, event: QtGui.QKeyEvent):
        print(event.key())
        return

class MainWindow(QtWidgets.QMainWindow):
    key_pressed = QtCore.pyqtSignal(QtGui.QKeyEvent)

    def __init__(self, *args, **kwargs):
        global traces, log_data, column_names

        #log_file_path = "samples/xcan_log_with_descriptions.txt"
        log_file_path = "samples/4_0-log.txt"
        filter_file_path = "filters/filter_VFX_XCAN.txt"
        trace_config_file_path = "trace_config.json"
        loadFile(log_file_path)
        loadFile(filter_file_path)
        loadFile(trace_config_file_path)
        apply_filters()
        add_trace_points()
        
        #Set up window
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("CAN Analyze v"+version)
        scriptDir = os.path.dirname(os.path.realpath(__file__))
        self.setWindowIcon(QtGui.QIcon(scriptDir + os.path.sep + 'images/icon.png'))

        #Set up matplotlib canvas widget
        sc = MplCanvas(self, width=5, height=4, dpi=100)
        #sc.axes.plot([0,1,2,3,4], [10,1,20,3,40])
      
        #Add traces
        for trace in traces:
            #Plot time on x axis and each trace on y with an offset to match order in trace_config file
            line, = sc.axes.step(x=log_data[:,0], y=log_data[:,column_names.index(trace["name"])] + 2*(len(traces) - traces.index(trace)))

        self.snap_cursor = SnappingCursor(sc.axes, line)
        sc.mpl_connect('motion_notify_event', self.snap_cursor.on_mouse_move)
        sc.mpl_connect('button_press_event', self.snap_cursor.on_mouse_click)
        self.key_pressed.connect(sc.onKeyPressEvent)
        #sc.mpl_connect('key_press_event', self.snap_cursor.on_press)
        #sc.keyPressed.connect(self.snap_cursor.on_press)
        #self.key_pressed.connect(self.snap_cursor.on_press)

        #Set up table widget
        self.table = QtWidgets.QTableView()
        #Show first 12 columns in the table
        #self.model = TableModel(df.iloc[:, :12])
        self.model = TableModel((log_data, column_names))
        self.table.setModel(self.model)
        self.table.resizeColumnsToContents()
        #self.table.resizeRowsToContents()

        # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
        toolbar = NavigationToolbar(sc, self)


        #Lay eveything out in the window
        left_panel_layout = QtWidgets.QVBoxLayout()
        left_panel_layout.addWidget(toolbar)
        left_panel_layout.addWidget(sc)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_panel_layout)
        main_layout.addWidget(self.table)

        # Create a placeholder widget to hold left and right panels.
        widget = QtWidgets.QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        self.showMaximized()
        
    def highlightRow(self,row):
        """
        Used to highlight row in QTableView after the corresponding point is clicked on the plot
        """  
        self.table.selectRow(row)
        self.table.scrollTo(self.table.model().index(row, 0),QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        print("Key event emitted")
        self.key_pressed.emit(event)
        return super().keyPressEvent(event)

appid = u'cananalyze.cananalyze.v'+version # application ID for Windows to set correct icon
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)


app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec()