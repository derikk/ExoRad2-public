import re

import numpy as np
import xlrd
from astropy import constants as cc
from astropy import units as u
from astropy.io import ascii

from exorad.log.logger import Logger
from exorad.models.source import Star, CustomSed

compactString = lambda string: string.replace(' ', '').replace('-', '').lower()
stripUnitString = lambda string: string.replace('[', '').replace(']', '')


class Target(Logger, object):
    '''
    Target base class
    '''

    def __init__(self):
        self.set_log_name()
        luminosity = None
        sed = None
        model = None
        table = None
        id = None
        star = None
        planet = None
        name = None

    def calc_logg(self, M, R):
        m = M.si
        r = R.si
        g = cc.G * m / r ** 2
        g = g.to(u.cm / u.s ** 2)

        return np.log10(g.value)

    def update_target(self, obj):
        if isinstance(obj, Star) or isinstance(obj, CustomSed):
            self.star.luminosity = obj.luminosity
            self.star.sed = obj.sed
            self.star.model = obj.model
            self.debug('target updated')
        else:
            self.warning(
                'Object type {:s} not implemented'.format(type(obj)))

    def write(self, output):
        targets_out = output.create_group('targets')
        group_name = str(self.name)
        target_dict = self.to_dict()
        targets_out.store_dictionary(target_dict, group_name=group_name)
        self.info('target {} saved'.format(self.name))
        return output

    def to_dict(self):
        from exorad.utils.util import to_dict
        return to_dict(self)


class BaseTargetList(Logger, object):

    def __init__(self):
        self.set_log_name()

        self.read_data()
        self._targets = self.create_target_list()

    def star_keys(self):
        raise NotImplementedError

    def star_data(self):
        raise NotImplementedError

    def read_data(self):
        raise NotImplementedError

    def create_target_list(self):

        star_keys = self.star_keys()

        star_data = self.star_data()

        # print(planet_data)
        # print(type(planet_data))
        # quit()
        planet_data = None
        planet_keys = None
        try:
            planet_keys = self.planet_keys()
            planet_data = self.planet_data()
        except: pass

        target_list = []
        if planet_data:
            for i,(star, planet) in enumerate(zip(star_data, planet_data)):
                target = Target()
                target.planet = Target()
                target.star = Target()

                planet_dict = dict(zip(planet_keys, planet))

                target.planet.__dict__.update(planet_dict)

                star_dict = dict(zip(star_keys, star))

                target.star.__dict__.update(star_dict)
                target.name = target.planet.name
                target.id = i

                target_list.append(target)
        else:
            for i, star in enumerate(star_data):
                target = Target()
                target.star = Target()
                target.id = i

                star_dict = dict(zip(star_keys, star))

                target.star.__dict__.update(star_dict)
                target.name = target.star.name

                target_list.append(target)
        return target_list

    @property
    def target(self):
        return self._targets

    def searchTarget(self, name):
        # method inspired from similar functionality in ExoData
        searchName = compactString(name)
        returnList = []

        for target in self.target:
            if re.search(searchName, compactString(str(target.star.name))) or re.search(searchName, compactString(
                    str(target.planet.name))):
                returnList.append(target)

        return returnList


class XLXSTargetList(BaseTargetList):
    star_data_columns = (1, 6)
    planet_data_columns = (8, 18)
    number_to_be_observed_column = 20
    data_row0 = 4
    units_row = 3

    def __init__(self, filename):
        self.filename = filename

        super().__init__()

    def __parseData__(self, col_range):
        Sheet = self.tmpSheet
        keys = Sheet.row_values(2)[col_range[0]:col_range[1] + 1]
        keys[0] = 'name'
        obj = {}

        for key, col in zip(keys, list(range(col_range[0], col_range[1] + 1))):
            str_unit = Sheet.cell_value(rowx=self.units_row, colx=col)
            if len(str_unit) > 0:
                try:
                    dim = u.Unit(stripUnitString(str_unit))
                except ValueError:
                    self.warning('Unrecognised physical units')
                    dim = 1
            else:
                dim = 1

            obj[key] = Sheet.col_values(col)[self.data_row0:] * dim

        return obj

    def planet_keys(self):
        return self.planet.keys()

    def star_keys(self):
        return self.star.keys()

    def planet_data(self):
        planet_list = list(self.planet.values())
        return list(map(list, zip(*planet_list)))

    def star_data(self):
        star_list = list(self.star.values())
        return list(map(list, zip(*star_list)))

    def read_data(self):

        xl_workbook = xlrd.open_workbook(self.filename)
        self.tmpSheet = xl_workbook.sheet_by_name('Sheet1')

        self.planet = self.__parseData__(col_range=self.planet_data_columns)
        self.planet['Nobs'] = self.tmpSheet.col_values(self.number_to_be_observed_column)[self.data_row0:]

        self.star = self.__parseData__(col_range=self.star_data_columns)


class CSVTargetList(BaseTargetList):
    def __init__(self, filename):
        self.filename = filename
        super().__init__()

    def read_data(self):
        self.tmpTab = ascii.read(self.filename, format="csv")

    def star_keys(self):
        s_col = [k for k in self.tmpTab.keys() if "star" in k]
        return [k.split(' ')[1] for k in s_col]

    def star_data(self):
        star_k = [k for k in self.tmpTab.keys() if "star" in k]
        units = []
        for n, k in enumerate(star_k):
            if len(k.split(' ')) == 3:
                un = k.split(' ')[2]
                units.append(1 * u.Unit(stripUnitString(un)))
            else:
                units.append(None)
        dat = []
        for i in range(len(self.tmpTab[star_k])):
            val = list(self.tmpTab[star_k][i])

            for n in range(len(val)):
                if units[n] is not None:
                    val[n] = val[n] * units[n]
            dat.append([str(x) if isinstance(x, np.str_) else x for x in val])
        return dat

    def planet_keys(self):
        s_col = [k for k in self.tmpTab.keys() if "planet" in k]
        return [k.split(' ')[1] for k in s_col]

    def planet_data(self):
        planet_k = [k for k in self.tmpTab.keys() if "planet" in k]
        units = []
        for n, k in enumerate(planet_k):
            if len(k.split(' ')) == 3:
                un = k.split(' ')[2]
                units.append(1 * u.Unit(stripUnitString(un)))
            else:
                units.append(None)
        dat = []
        for i in range(len(self.tmpTab[planet_k])):
            val = list(self.tmpTab[planet_k][i])

            for n in range(len(val)):
                if units[n] is not None:
                    val[n] = val[n] * units[n]
            dat.append([str(x) if isinstance(x, np.str_) else x for x in val])
        return dat


class OldExcelTargetList(Logger, object):
    star_data_columns = (1, 6)
    number_to_be_observed_column = 20
    data_row0 = 4
    units_row = 3

    def __init__(self, filename):

        self.set_log_name()

        if filename.endswith('.xlsx'):
            xl_workbook = xlrd.open_workbook(filename)

            tmpSheet = xl_workbook.sheet_by_name('Sheet1')
            tmpSheet = tmpSheet

            star = self.__parseData__(tmpSheet, col_range=self.star_data_columns)

            key0 = list(star.keys())[0]
            n_targets = len(star[key0])

            self.target = [Target() for k in range(n_targets)]
            for k, target in enumerate(self.target):
                setattr(target, 'star', Target())
                for key in list(star.keys()):
                    setattr(target.star, key, star[key][k])
        else:
            self.error("Wrong target list format")
            raise IOError("Wrong target list format")

    def __parseData__(self, Sheet, col_range):
        keys = Sheet.row_values(2)[col_range[0]:col_range[1] + 1]
        keys[0] = 'name'
        obj = {}

        for key, col in zip(keys, list(range(col_range[0], col_range[1] + 1))):
            str_unit = Sheet.cell_value(rowx=self.units_row, colx=col)
            if len(str_unit) > 0:
                try:
                    dim = u.Unit(stripUnitString(str_unit))
                except ValueError:
                    self.warning('Unrecognised physical units')
                    dim = 1
            else:
                dim = 1

            obj[key] = Sheet.col_values(col)[self.data_row0:] * dim

        return obj

    def searchTarget(self, name):
        # method inspired from similar functionality in ExoData
        searchName = compactString(name)
        returnList = []

        for target in self.target:
            if re.search(searchName, compactString(str(target.star.name))) or re.search(searchName, compactString(
                    str(target.planet.name))):
                returnList.append(target)

        return returnList
