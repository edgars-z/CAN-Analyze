import ctypes
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

version = u"0.1.1"

matplotlib.use('QtAgg')


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
                #return str(self._data.columns[section])
                return self.column_names[section]

            if orientation == Qt.Orientation.Vertical:
                #return str(self._data.index[section]+1)               
                #return list(range(1,len(self._data)+1))[section]
                return section+1


class TableView(QtWidgets.QTableView):
    
    def __init__(self):
        super(TableView, self).__init__()
        
    def keyPressEvent(self, event):
        """Reimplement Qt method"""
        print("TableView keypress: ",event.key())
        if event.matches(QtGui.QKeySequence.StandardKey.Copy):
            #self.copy()
            print("Ctrl + C from TableView")
            event.accept()
        else:
            QtWidgets.QTableView.keyPressEvent(self, event)

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

    def on_press(self, event):
        print("keypress detected in matplotlib canvas:")
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
        if event.inaxes:
            #print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %   ('double' if event.dblclick else 'single', event.button,           event.x, event.y, event.xdata, event.ydata))
            index = min(np.searchsorted(self.x, event.xdata), len(self.x) - 1)
            #print("Row: ", index)
            w.highlightRow(index)


class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)



class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        global traces, log_data, column_names, filter_list

        #Set up window
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("CAN Analyze v"+version)
        self.setAcceptDrops(True)
        scriptDir = os.path.dirname(os.path.realpath(__file__))
        self.setWindowIcon(QtGui.QIcon(scriptDir + os.path.sep + "images/icon.png"))
        default_filter_file_path = scriptDir + os.path.sep + "filters/filter_default.txt"
        default_trace_config_file_path = scriptDir + os.path.sep + "config/trace_config.json"

        self.dh = DataHandler(["Time", "Delta", "Description", "ID", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "Colour"])

        #TODO: handle startup with nothing loaded
        #TODO: enable loading at any point during runtime
        #TODO: handle multiple log files loaded at once

        #Open dialog to load one or more files
        loaded_files, _ = QtWidgets.QFileDialog.getOpenFileNames(self,"Open log file, filter file or trace configuration", "","All Files (*);;Logs or filters (*.txt);;Trace configurations (*.json)")

        for loaded_file in loaded_files:
            self.dh.load_file(loaded_file)

        #Check if any filters or traces were loaded. If not, then load defaults
        if len(self.dh.filter_list) == 0:
            self.dh.load_file(default_filter_file_path)
        if len(self.dh.traces) == 0:
            self.dh.load_file(default_trace_config_file_path)

        #TODO call these after loading new files. From inside DataHandler?
        #self.dh.apply_filters()
        #self.dh.add_trace_points()
        


        #Set up matplotlib canvas widget
        sc = MplCanvas(self, width=5, height=4, dpi=100)
        #Must set focus policy for keyboard events to be propagated
        sc.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus) 

        #Add traces
        for trace in self.dh.traces:
            #Plot time on x axis and each trace on y with an offset to match order in trace_config file
            line, = sc.axes.step(x=self.dh.log_data[:,0], y=self.dh.log_data[:,self.dh.column_names.index(trace["name"])] + 2*(len(self.dh.traces) - self.dh.traces.index(trace)))

        self.snap_cursor = SnappingCursor(sc.axes, line)
        sc.mpl_connect('motion_notify_event', self.snap_cursor.on_mouse_move)
        sc.mpl_connect('button_press_event', self.snap_cursor.on_mouse_click)
        sc.mpl_connect('key_press_event', self.snap_cursor.on_press)

        #Set up table widget
        self.table = TableView() 
        #Show first 12 columns in the table
        self.model = TableModel((self.dh.log_data, self.dh.column_names))
        self.table.setModel(self.model)

        #Resize table to fit contents
        self.table.setVisible(False)
        self.table.resizeColumnsToContents()
        self.table.verticalHeader().setDefaultSectionSize(self.table.fontMetrics().height())
        self.table.setVisible(True)

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

    def keyPressEvent(self, event):
        """Reimplement Qt method"""
        print(event.key())
        #if event.matches(QtGui.QKeySequence.StandardKey.Copy):
        #    #self.copy()
        #    print("Ctrl + C from TableView")
        #    event.accept()
        #else:
        QtWidgets.QMainWindow.keyPressEvent(self, event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            self.dh.load_file(f)


if sys.platform.startswith("win32"):
    appid = u'cananalyze.cananalyze.v'+version # application ID for Windows to set correct icon
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec()