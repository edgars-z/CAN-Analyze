import ctypes
import csv
import io
import os
import sys
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import \
    NavigationToolbar2QT as NavigationToolbar

from DataHandler import DataHandler

version = u"0.1.2"

matplotlib.use('QtAgg')


class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data[0]
        self.column_names = data[1]

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
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
            if index.column() == self.column_names.index("Description"):
                value = self._data[index.row()]
                row_colour = value[self.column_names.index("Colour")]
                (r,g,b) = (255, 255, 255)
                if row_colour > "":
                    #If a colour value is defined for this row, work out corresponding RGB value and apply it
                    # // ---Colors from CanView---
                    match row_colour:
                        case "RED":
                            (r,g,b) = (220, 0, 0)
                        case "GREEN":
                            (r,g,b) = (0, 220, 0)
                        case "BLUE":
                            (r,g,b) = (0, 128, 255)
                        case "YELLOW":
                            (r,g,b) = (255, 255, 0)
                        case "GREY": 
                            (r,g,b) = (190, 190, 190)
                        case "PURPLE":
                            (r,g,b) = (255, 0, 255)
                        case "ORANGE":
                            (r,g,b) = (255, 128, 64)
                        case "PINK":
                            (r,g,b) = (255, 100, 177)
                        case "LIGHT_RED":
                            (r,g,b) = (255, 125, 125)
                        case "LIGHT_GREEN":
                            (r,g,b) = (213, 255, 213)
                        case "LIGHT_BLUE":
                            (r,g,b) = (170, 213, 255)
                        case "LIGHT_YELLOW":
                            (r,g,b) = (255, 255, 190)
                        case "LIGHT_GREY":
                            (r,g,b) = (223, 223, 223)
                        case "LIGHT_PURPLE":
                            (r,g,b) = (255, 150, 255)
                        case "LIGHT_ORANGE":
                            (r,g,b) = (255, 165, 121)
                        case "LIGHT_PINK":
                            (r,g,b) = (255, 170, 213)
                        case _:
                            (r,g,b) = (255, 255, 255)

            elif index.column() == self.column_names.index("ID"):
                #CAN msg ID background light green rgb(200, 255, 200).
                (r,g,b) = (200, 255, 200)

            else:
                (r,g,b) = (255, 255, 255)

            return QtGui.QColor.fromRgb(r,g,b)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section < len(self.column_names):
                    return self.column_names[section]
                else:
                    return section+1

            if orientation == Qt.Orientation.Vertical:
                return section+1


class TableView(QtWidgets.QTableView):
    
    def __init__(self):
        super(TableView, self).__init__()
        
    def keyPressEvent(self, event):
        """Reimplement Qt method"""
        print("TableView keypress: ",event.key())
        if event.matches(QtGui.QKeySequence.StandardKey.Copy):
            print("Ctrl + C from TableView")
            clipboard.setText("test copy")
            selection = self.selectedIndexes()
            if selection:
                rows = sorted(index.row() for index in selection)
                columns = sorted(index.column() for index in selection)
                rowcount = rows[-1] - rows[0] + 1
                colcount = columns[-1] - columns[0] + 1
                table = [[''] * colcount for _ in range(rowcount)]
                for index in selection:
                    row = index.row() - rows[0]
                    column = index.column() - columns[0]
                    table[row][column] = index.data()
                stream = io.StringIO()
                csv.writer(stream).writerows(table)
                clipboard.setText(stream.getvalue())
            event.accept()
        else:
            QtWidgets.QTableView.keyPressEvent(self, event)


class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)

        self.x = []
        self._last_index = None
        self.text = self.axes.text(0.0, 0.0, '', va="center", ha="center")
        self.measured_value_text = self.axes.text(0.0, 0.0, '', va="center", ha="center")
        self.measured_value_text.set_visible(False)

        self.axes.set_yticklabels("",ha = "right", va = "bottom")
        self.axes.yaxis.set_major_formatter(self.y_label_formatter)
        self.axes.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        

        super(MplCanvas, self).__init__(self.fig)

    def remove_traces(self):
        #Remove any existing traces lines from the plot
        for line in self.axes.get_lines():
            line.remove()
        self.trace_count = 1
        self.trace_labels = [""]

    def initialize_cursor_snapping(self, line):
        #This is the list to which the cursor will snap
        self.x = line.get_xdata()

        #Before adding any other lines, collect data about traces that have been added so far
        self.trace_count = len(self.axes.get_lines())
        self.trace_labels = []
        for line in self.axes.get_lines():
            self.trace_labels.append(line.get_label())

        #Define vertical cursor line and measurement lines
        self.vertical_line = self.axes.axvline(color='k', lw=0.8, ls='--')
        self.measurement_start_line = self.axes.axvline(color='red', lw=2, ls='-')
        self.measurement_end_line = self.axes.axvline(color='red', lw=2, ls='-')
        self.measurement_start_line.set_visible(False)
        self.measurement_end_line.set_visible(False)
        self.measurement_step = 0
        self.measured_value = 0

        self.fig.tight_layout()


    def y_label_formatter(self, tick_val, tick_pos):
        yval_range = range(2*self.trace_count, 1, -2)
        if int(tick_val) in yval_range:
            return self.trace_labels[yval_range.index(int(tick_val))]
        else:
            return ''

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
                self.axes.figure.canvas.draw()
        else:
            self.set_cross_hair_visible(True)
            x, y = event.xdata, event.ydata

            #find index of the nearest match in the data to snap to            
            self.current_index = min(np.searchsorted(self.x, x), len(self.x) - 1)
            if self.current_index>0 and (abs(self.x[self.current_index] - x) > abs(self.x[self.current_index-1] - x)):
                self.current_index -=1

            if self.current_index == self._last_index:
                return  # still on the same data point, no update needed
            self._last_index = self.current_index
            x = self.x[self.current_index]
    
            # update snapline position
            self.vertical_line.set_xdata([x])
            # show current time and line number in log
            self.text.set_text('t=%1.2f ms\nLine %d' % (x,self.current_index+1))
            self.text.set_position((x,0))
            self.axes.figure.canvas.draw()

    def on_press(self, event):
        print("keypress detected in matplotlib canvas:")
        if event.key == " ":
            print("spacebar")
            if not event.inaxes:
                #press spacebar outside the graph to clear measurement lines
                self.measurement_start_line.set_visible(False)
                self.measurement_end_line.set_visible(False)
                self.measured_value_text.set_visible(False)
                self.axes.figure.canvas.draw()
                self.measurement_step = 0 
            else:
                if self.measurement_step == 0:
                    #press spacear once to set the first measurement line
                    self.measurement_start_line.set_xdata(self.vertical_line.get_xdata())
                    self.measurement_start_line.set_visible(True)
                    self.axes.figure.canvas.draw()  
                    self.measurement_step += 1

                elif self.measurement_step == 1:
                    #press spacebar twice to set the second measurement line and display measured value
                    self.measurement_end_line.set_xdata(self.vertical_line.get_xdata())
                    self.measurement_end_line.set_visible(True)
                    self.measured_value = self.measurement_end_line.get_xdata()[0] - self.measurement_start_line.get_xdata()[0]
                    self.measured_value_text.set_text('Δt = %1.2f ms' % abs(self.measured_value))
                    self.measured_value_text.set_position(((self.measurement_end_line.get_xdata()[0]+self.measurement_start_line.get_xdata()[0])/2, 0))
                    self.measured_value_text.set_visible(True)
                    self.axes.figure.canvas.draw()  
                    self.measurement_step += 1
                else:
                    #press spacebar again to clear measurement
                    self.measurement_start_line.set_visible(False)
                    self.measurement_end_line.set_visible(False)
                    self.measured_value_text.set_visible(False)
                    self.axes.figure.canvas.draw()  
                    self.measurement_step = 0
        else:
            print(event.key)

    def on_mouse_click(self, event):
        if event.inaxes:
            w.highlightRow(self.current_index)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        global traces, log_data, column_names, filter_list

        #Set up window
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("CAN Analyze v"+version)
        self.setAcceptDrops(True)
        scriptDir = os.path.dirname(os.path.realpath(__file__))
        self.setWindowIcon(QtGui.QIcon(scriptDir + os.path.sep + "images/icon.png"))
        self.default_filter_file_path = scriptDir + os.path.sep + "filters/filter_default.txt"
        self.default_trace_config_file_path = scriptDir + os.path.sep + "config/trace_config_default.json"

        self.dh = DataHandler(["Time", "Delta", "Description", "ID", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "Colour"])

        #TODO: handle startup with nothing loaded
        #TODO: enable loading at any point during runtime
        #TODO: handle multiple log files loaded at once





        #Set up matplotlib canvas widget
        self.mpl_canvas = MplCanvas(self, width=5, height=4, dpi=100)
        #Must set focus policy for keyboard events to be propagated
        self.mpl_canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus) 




        #self.snap_cursor = SnappingCursor(self.mpl_canvas.axes, line)
        self.mpl_canvas.mpl_connect('motion_notify_event', self.mpl_canvas.on_mouse_move)
        self.mpl_canvas.mpl_connect('button_press_event', self.mpl_canvas.on_mouse_click)
        self.mpl_canvas.mpl_connect('key_press_event', self.mpl_canvas.on_press)




        #Set up table widget
        self.table = TableView()        

        #Open dialog to load one or more files
        self.load_file_dialog()

        #Resize table to fit contents
        self.table.setVisible(False)
        self.table.resizeColumnsToContents()
        self.table.verticalHeader().setDefaultSectionSize(self.table.fontMetrics().height())
        self.table.setVisible(True)

        # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
        toolbar = NavigationToolbar(self.mpl_canvas, self)


        #Lay eveything out in the window
        left_panel_layout = QtWidgets.QVBoxLayout()
        left_panel_layout.addWidget(toolbar)
        left_panel_layout.addWidget(self.mpl_canvas)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_panel_layout)
        main_layout.addWidget(self.table)

        # Create a placeholder widget to hold left and right panels.
        widget = QtWidgets.QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        self.showMaximized()

    def load_file_dialog(self):
        loaded_files, _ = QtWidgets.QFileDialog.getOpenFileNames(self,"Open log file, filter file or trace configuration", "","All Files (*);;Logs or filters (*.txt);;Trace configurations (*.json)")
        if len(loaded_files) > 0:
            for loaded_file in loaded_files:
                self.dh.load_file(loaded_file)
            self.process_loaded_file()

    def process_loaded_file(self):
        #Check if any filters or traces have been loaded. If not, then load defaults
        if len(self.dh.filter_list) == 0:
            self.dh.load_file(self.default_filter_file_path)
        if len(self.dh.traces) == 0:
            self.dh.load_file(self.default_trace_config_file_path)
        
        #Add traces
        self.add_traces_to_canvas()

        #Add data to table
        self.model = TableModel((self.dh.log_data, self.dh.column_names))
        self.table.setModel(self.model)

    def add_traces_to_canvas(self):
        """Clears matplotlib canvas and adds each of the currently defined traces to the canvas
        """
        self.mpl_canvas.remove_traces()
        for trace in self.dh.traces:
            #Plot time on x axis and each trace on y with an offset to match order in trace_config file
            line, = self.mpl_canvas.axes.step(x = self.dh.log_data[:,0],
                                              y = self.dh.log_data[:,self.dh.column_names.index(trace["name"])] + 2*(len(self.dh.traces) - self.dh.traces.index(trace)),
                                              label = trace["name"]
                                              )
        self.mpl_canvas.initialize_cursor_snapping(line)
        
    def highlightRow(self,row):
        """
        Used to highlight row in QTableView after the corresponding point is clicked on the plot
        """  
        self.table.selectRow(row)
        self.table.scrollTo(self.table.model().index(row, 0),QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)

    def keyPressEvent(self, event):
        """Reimplement Qt method"""
        print("MainWindow keypress: %s" % event.key())
        if event.matches(QtGui.QKeySequence.StandardKey.Open):
            print("Ctrl + O in MainWindow")
            self.load_file_dialog()
            event.accept()
        else:
            QtWidgets.QMainWindow.keyPressEvent(self, event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        dropped_files = [u.toLocalFile() for u in event.mimeData().urls()]
        if len(dropped_files) > 0:
            for dropped_file in dropped_files:
                self.dh.load_file(dropped_file)
            self.process_loaded_file()



if sys.platform.startswith("win32"):
    appid = u'cananalyze.cananalyze.v'+version # application ID for Windows to set correct icon
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

app = QtWidgets.QApplication(sys.argv)
clipboard = app.clipboard()
w = MainWindow()
app.exec()