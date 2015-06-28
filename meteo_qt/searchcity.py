from PyQt5.QtCore import (
    QTimer, pyqtSignal, QThread, QSettings, QByteArray, QCoreApplication
    )
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget,
    QLabel
    )
import urllib.request
from lxml import etree
from socket import timeout
import logging

class SearchCity(QDialog):
    id_signal = pyqtSignal([tuple])
    city_signal = pyqtSignal([tuple])
    country_signal = pyqtSignal([tuple])

    def __init__(self, accurate_url, parent=None):
        super(SearchCity, self).__init__(parent)
        self.settings = QSettings()
        self.delay = 1000
        self.search_string = self.tr('Searching...')
        self.timer = QTimer()
        self.accurate_url = accurate_url
        self.suffix = '&type=like&mode=xml'
        self.layout = QVBoxLayout()
        self.lineLayout = QHBoxLayout()
        self.buttonSearch = QPushButton()
        self.buttonSearch.setIcon(QIcon(':/find'))
        self.buttonSearch.clicked.connect(self.search)
        self.line_search = QLineEdit(QCoreApplication.translate(
            'Search city dialog','Start typing the city...',''))
        self.line_search.selectAll()
        self.listWidget = QListWidget()
        self.status = QLabel()
        self.lineLayout.addWidget(self.line_search)
        self.lineLayout.addWidget(self.buttonSearch)
        self.layout.addLayout(self.lineLayout)
        self.layout.addWidget(self.listWidget)
        self.layout.addWidget(self.status)
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.addStretch()
        self.buttonOk = QPushButton(self.tr('&Ok'))
        self.buttonOk.setEnabled(False)
        self.buttonCancel = QPushButton(self.tr('&Cancel'))
        self.buttonLayout.addWidget(self.buttonOk)
        self.buttonLayout.addWidget(self.buttonCancel)
        self.layout.addLayout(self.buttonLayout)
        self.setMinimumWidth(int(len(self.line_search.text())*20))
        self.setLayout(self.layout)
        self.line_search.returnPressed.connect(self.search)
        self.line_search.textChanged.connect(self.timer_run)
        self.buttonOk.clicked.connect(self.accept)
        self.buttonCancel.clicked.connect(self.reject)
        self.listWidget.itemSelectionChanged.connect(self.buttonCheck)
        self.listWidget.itemDoubleClicked['QListWidgetItem *'].connect(
            self.accept)
        self.restoreGeometry(self.settings.value("SearchCity/Geometry",
                QByteArray()))
        self.timer_search = QTimer(self)
        self.timer_search.timeout.connect(self.search)

    def timer_run(self):
        self.timer_search.start(1000)

    def closeEvent(self, event):
        self.settings.setValue("SearchCity/Geometry", self.saveGeometry())

    def moveEvent(self, event):
        self.settings.setValue("SearchCity/Geometry", self.saveGeometry())

    def resizeEvent(self, event):
        self.settings.setValue("SearchCity/Geometry", self.saveGeometry())

    def buttonCheck(self):
        '''Enable OK button if an item is selected'''
        row = self.listWidget.currentRow()
        item = self.listWidget.item(row)
        if item != None:
            self.buttonOk.setEnabled(True)

    def accept(self):
        row = self.listWidget.currentRow()
        item = self.listWidget.item(row)
        if item != None:
            selected_city = item.text()
            city_list = selected_city.split(' - ')
            for c in range(len(city_list)):
                city_list[c] = city_list[c].strip()
            id_ = 'ID', city_list[0]
            city = 'City', city_list[1]
            country = 'Country', city_list[2]
            self.id_signal[tuple].emit(id_)
            self.city_signal[tuple].emit(city)
            self.country_signal[tuple].emit(country)
        QDialog.accept(self)

    def thread_terminate(self):
        if hasattr(self, 'workThread'):
            if self.workThread.isRunning():
                self.workThread.terminate()

    def search(self):
        self.timer_search.stop()
        self.city = (self.line_search.text())
        self.thread_terminate()
        if len(self.city) < 3:
            self.status.setText(self.tr('Please type more than three letters'))
            return
        self.lista=[]
        self.errorStatus = False
        self.buttonOk.setEnabled(False)
        self.listWidget.clear()
        self.status.setText(self.search_string)
        self.workThread = WorkThread(self.accurate_url, self.city, self.suffix)
        self.workThread.setTerminationEnabled(True)
        self.workThread.city_signal['QString'].connect(self.addlist)
        self.workThread.finished.connect(self.result)
        self.workThread.error['QString'].connect(self.error)
        self.workThread.searching['QString'].connect(self.searching)
        self.workThread.started.connect(self.thread_started)
        self.timer.singleShot(self.delay, self.threadstart)

    def searching(self, message):
        '''Display a status message when searching takes a while'''
        self.status.setText(message)

    def thread_started(self):
        '''Force the "searching" status message'''
        self.status.setText(self.search_string)

    def threadstart(self):
        self.workThread.start()

    def addlist(self, city):
        logging.debug('Found: ' + str(city))
        if city not in self.lista:
            self.lista.append(city)

    def error(self, e):
        self.delay = 2000
        logging.error(e)
        self.status.setText(e)
        self.adjustSize()
        self.errorStatus = True

    def result(self):
        if self.errorStatus:
            return
        if len(self.line_search.text()) < 3:
            self.thread_terminate()
            self.status.clear()
            return
        self.delay = 1000
        # Clear the listWidget elements from an interrupted thread
        self.listWidget.clear()
        self.listWidget.addItems(self.lista)
        number_cities = len(self.lista)
        cities_text = ''
        if number_cities == 0:
            cities_text = self.tr('No results')
        elif number_cities == 1:
            cities_text = self.tr('Found {0} city').format(number_cities)
        elif number_cities > 1:
            cities_text = self.tr('Found {0} cities').format(number_cities)
        self.status.setText(cities_text)


class WorkThread(QThread):
    error = pyqtSignal(['QString'])
    city_signal = pyqtSignal(['QString'])
    searching = pyqtSignal(['QString'])

    def __init__(self, accurate_url, city, suffix, parent=None):
        QThread.__init__(self, parent)
        self.accurate_url = accurate_url
        # Search in any language
        self.city = city#self.encode_utf8(city)
        self.suffix = suffix
        self.tentatives = 1

    def run(self):
        error_message = self.tr(
                'Data error, please try again later\nor modify the name of the city')
        self.lista = []
        if self.city == '':
            return
        try:
            logging.info(self.accurate_url + repr(self.city.encode('utf-8')).replace(
                    "b'","").replace("\\x","%").replace("'","") + self.suffix)
            logging.debug('City before utf8 encode :' + self.accurate_url + self.city + self.suffix)
            req = urllib.request.urlopen(
                self.accurate_url + repr(self.city.encode('utf-8')).replace(
                    "b'","").replace("\\x","%").replace("'","") + self.suffix, timeout=5)
            page = req.read()
            tree = etree.fromstring(page)
        except timeout:
            if self.tentatives == 10:
                logging.error(error_message)
                return
            else:
                self.tentatives += 1
                searching_message = self.tr('Please wait, searching...')
                logging.debug(searching_message)
                self.searching['QString'].emit(searching_message)
                self.run()
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            code = ''
            if hasattr(error, 'code'):
                code = str(error.code)
            m_error = (self.tr('Error: ') + code + ' ' + str(error.reason) +
                       self.tr('\nTry again later'))
            if self.tentatives == 10:
                self.error['QString'].emit(m_error)
                return
            else:
                self.tentatives += 1
                logging.debug('Tries: ' + str(self.tentatives))
                self.run()
        # No result
        try:
            if int(tree[1].text) == 0:
                logging.debug('Number of cities: 0')
                if self.tentatives == 10:
                    return
                else:
                    self.tentatives += 1
                    logging.debug('Tries: '  + str(self.tentatives))
                    logging.debug('Try to retreive city information...')
                    self.run()
        except:
            return
        for i in range(int(tree[1].text)):
            city = tree[3][i][0].get('name')
            country = tree[3][i][0][1].text
            id_ = tree[3][i][0].get('id')
            if int(id_) == 0:
                logging.error('Error ID: ' + str(id_))
                if self.tentatives == 10:
                    self.error['QString'].emit(error_message)
                    return
                else:
                    self.tentatives += 1
                    logging.debug('Tries: ' + str(self.tentatives))
                    logging.debug('Try to retreive city information...')
                    # Try with a fuzzy city name
                    if city != '':
                        logging.info('Change search to:' + city)
                        self.city = repr(city.encode('utf-8')).replace(
                    "b'","").replace("\\x","%").replace("'","")
                    self.run()
            if city == '' or country == None:
                if self.tentatives == 10:
                    self.error['QString'].emit(error_message)
                    return
                else:
                    self.tentatives += 1
                    logging.debug('Tries: ' + str(self.tentatives))
                    logging.debug('Try to retreive city information...')
                    self.run()
            try:
                if id_ == '0':
                    continue
                place = (id_ + ' - ' + city + ' - ' + country)
                if place in self.lista:
                    continue
                self.lista.append(place)
            except:
                logging.critical('An error has occured:')
                logging.critical('ID' + str(id_))
                logging.critical('City' + str(city))
                logging.critical('Country' + str(country))
                return
        for i in self.lista:
            self.city_signal['QString'].emit(i)
        logging.debug('City thread done')
        return

