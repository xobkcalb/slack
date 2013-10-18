import os
import re
import sys
from PyQt4 import QtCore, QtGui, uic, Qsci

def _clickedFixer(callback):
    def _wrapper(self, is_pressed = None):
        if is_pressed is None:
            callback(self)
    return _wrapper

WORD_RE = re.compile(r'\b[a-zA-Z_]\w*\b')
WORD_BLK_RE = re.compile(r'\b[a-zA-Z_]\w*(?:-[a-zA-Z_]\w*)*\b')
def parseFile(path):
    words_map = {}
    
    line_num = 1
    regexp = WORD_BLK_RE if path.endswith('.blk') or path.endswith('.nut') else WORD_RE
    with open(path) as f:
        for line in f:
            words = set(re.findall(regexp, line))
            for word in words:
                words_map.setdefault(word, []).append(line_num)
            line_num += 1
    
    return words_map.items()

def readFileLine(path, line_num):
    with open(path) as f:
        return f.readlines()[line_num - 1].rstrip()

def getPathExt(path):
    return os.path.splitext(path)[1]

class WordsProcessor:
    def __init__(self, path_list):
        self.path_list = path_list
        self.words_map = {}
        
        print '%d files to process' % len(path_list)
        i = 1
        for path in path_list:
            if i % 100 == 0:
                print '%d/%d' % (i, len(path_list))
            i += 1
            #print 'processing %s...' % path
            words = parseFile(path)
            for word, line_nums in words:
                self.words_map.setdefault(word, {})[path] = line_nums
        

class Main(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        uic.loadUi('slack.ui', self)
        self.folderPathEdit.setText(r'D:\dagor2\skyquake\prog')
        self.show()
        
        self.processor = None
        self.is_history_changing = False
        self.historyPath = 'words.txt'
        if os.path.exists(self.historyPath):
            with open(self.historyPath) as f:
                self.wordsHistory = [s.strip() for s in f.readlines() if s.strip()]
            self._fillHistoryCombobox()
        else:
            self.wordsHistory = []
        
        for checkbox in [self.nutCheckBox, self.blkCheckBox, self.headersCheckBox, self.sourcesCheckBox]:
            checkbox.toggled.connect(self.on_extensionCheckBox_toggled)
        
        self.fileEditor.setFont(QtGui.QFont('Courier New'))
        self.fileEditor.setMarginWidth(1, '999999')
        self.fileEditor.setMarginLineNumbers(1, True)
        self.fileEditor.setCaretLineVisible(True)
    
    def _fillHistoryCombobox(self):
        self.historyComboBox.clear()
        self.historyComboBox.addItems(QtCore.QStringList([''] + self.wordsHistory))
    
    @_clickedFixer
    def on_selectFolderButton_clicked(self):
        newFolderPath = QtGui.QFileDialog.getExistingDirectory(self, directory = self.folderPathEdit.text())
        if newFolderPath:
            self.folderPathEdit.setText(newFolderPath)

    def _getRoot(self):
        return str(self.folderPathEdit.text())
    
    def _getAllowedExtensions(self, get_all = False):
        result = []
        if get_all or self.nutCheckBox.isChecked():
            result.extend([ '.nut' ])
        if get_all or self.blkCheckBox.isChecked():
            result.extend([ '.blk' ])
        if get_all or self.headersCheckBox.isChecked():
            result.extend([ '.h', '.hpp' ])
        if get_all or self.sourcesCheckBox.isChecked():
            result.extend([ '.c', '.cpp' ])
        return result
    
    def on_extensionCheckBox_toggled(self, is_checked):
        self._refreshTree()
    
    @_clickedFixer
    def on_processButton_clicked(self):
        path_root = self._getRoot()
        
        path_list = []
        allowed_extensions = self._getAllowedExtensions(get_all = True)

        for root, dirs, files in os.walk(path_root):
            for forbidden in ['.git', 'CVS']:
                if forbidden in dirs:
                    dirs.remove(forbidden)
            
            for f in files:
                ext = getPathExt(f)
                if ext not in allowed_extensions:
                    continue
                path = os.path.join(root, f)
                path_list.append(path)
        path_list.sort()
        
        self.processor = WordsProcessor(path_list)
        self._refreshTree()
    
    def _getFilterText(self):
        return str(self.quickFindEdit.text())
    
    @staticmethod
    def _isWordFitting(word, filterText):
        if not filterText:
            return True
        if filterText.startswith('*'):
            filterText = filterText[1:].lower()
            word = word.lower()
        if filterText.startswith('"'):
            filterText = filterText[1:]
            return word == filterText
        else:
            return filterText in word
    
    def _refreshTree(self):
        if not self.processor:
            return
        filterText = self._getFilterText()
        allowed_extensions = self._getAllowedExtensions()
        
        self.wordsTree.clear()
        for word in sorted(self.processor.words_map.keys(), cmp = lambda a, b: cmp(a.lower(), b.lower())):
            if not self._isWordFitting(word, filterText):
                continue
            
            path_info = self.processor.words_map[word]
            path_list = [path for path in path_info.keys() if getPathExt(path) in allowed_extensions]
            if not path_list:
                continue
            
            adding_item = QtGui.QTreeWidgetItem( self.wordsTree, QtCore.QStringList([ word ]) )
            for path in sorted(path_list):
                line_nums = path_info[path]
                QtGui.QTreeWidgetItem( adding_item, QtCore.QStringList([ '%s (%d)' % (path, len(line_nums)) ]) )

            adding_item.setExpanded(self.expandCheckbox.isChecked())
        self.linesTree.clear()
    
    def on_quickFindEdit_returnPressed(self):
        filterText = self._getFilterText()
        if filterText and filterText not in self.wordsHistory:
            self.is_history_changing = True
            self.wordsHistory.append(filterText)
            with open(self.historyPath, 'w') as f:
                f.write('\n'.join(self.wordsHistory))
            self._fillHistoryCombobox()
            self.historyComboBox.setCurrentIndex(self.historyComboBox.count() - 1)
            self.is_history_changing = False
        self._refreshTree()
    
    def on_historyComboBox_currentIndexChanged(self, param):
        if self.is_history_changing or isinstance(param, int):
            return
        self.quickFindEdit.setText(param)
        self._refreshTree()
    
    def on_expandCheckbox_toggled(self, is_checked):
        for i in range(self.wordsTree.topLevelItemCount()):
            tree_item = self.wordsTree.topLevelItem(i)
            tree_item.setExpanded(is_checked)
    
    def on_wordsTree_currentItemChanged(self, current, previous):
        if not current:
            return
        self.linesTree.clear()
        
        word_item = current.parent()
        if not word_item:
            word_item = current
        word = str(word_item.text(0))
        allowed_extensions = self._getAllowedExtensions()
        
        path_info = self.processor.words_map[word]
        path_root = self._getRoot()
        for path in sorted(path_info.keys()):
            ext = getPathExt(path)
            if ext not in allowed_extensions:
                continue
            
            line_nums = path_info[path]
            adding_item = QtGui.QTreeWidgetItem( self.linesTree, QtCore.QStringList([ path[len(path_root)+1:], '' ]) )
            for line_num in line_nums:
                line = readFileLine(path, line_num)
                new_child = QtGui.QTreeWidgetItem( adding_item, QtCore.QStringList([ '%d:' % line_num, line ]) )
                new_child.setFont(1, QtGui.QFont('Courier New', weight = QtGui.QFont.Bold))
            
            adding_item.setExpanded(True)
    
    def on_linesTree_currentItemChanged(self, current, previous):
        if not current or not current.parent():
            return
        pathElement = current.parent()
        
        path = os.path.join(self._getRoot(), str(pathElement.text(0)))
        line = int(str(current.text(0))[:-1])
        
        with open(path) as f:
            self.fileEditor.setText(f.read())
            self.fileEditor.setCursorPosition(line - 1, 0)
            self.fileEditor.setFocus(QtCore.Qt.OtherFocusReason)
    
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = Main()
    sys.exit(app.exec_())
