import iss.find_spots.test as find_spots
import iss.extract.test as extract
import iss.utils.test as utils
import iss.stitch.test as stitch
import iss.setup.test as setup
import iss.pcr.test as pcr
import iss.call_spots.test as call_spots
import unittest


def suite_utils():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(utils.TestMorphology, 'test'))
    return suite


def suite_setup():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(setup.TestConfig, 'test'))
    suite.addTest(unittest.makeSuite(setup.TestNotebook, 'test'))
    suite.addTest(unittest.makeSuite(setup.TestTilePos, 'test'))
    return suite


def suite_extract():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(extract.TestFstack, 'test'))
    suite.addTest(unittest.makeSuite(extract.TestStripHack, 'test'))
    return suite


def suite_find_spots():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(find_spots.TestBase, 'test'))
    suite.addTest(unittest.makeSuite(find_spots.TestNeighbour, 'test'))
    return suite


def suite_stitch():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(stitch.TestShift, 'test'))
    suite.addTest(unittest.makeSuite(stitch.TestTileOrigin, 'test'))
    return suite


def suite_pcr():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(pcr.TestGetTransform, 'test'))
    suite.addTest(unittest.makeSuite(pcr.TestGetAverageTransform, 'test'))
    suite.addTest(unittest.makeSuite(pcr.TestIterate, 'test'))
    return suite


def suite_call_spots():
    suite = unittest.TestSuite()
    #suite.addTest(unittest.makeSuite(call_spots.TestScaledKMeans, 'test'))
    suite.addTest(unittest.makeSuite(call_spots.TestGetBleedMatrix, 'test'))
    #suite.addTest(unittest.makeSuite(call_spots.TestGetDyeChannelIntensityGuess, 'test'))
    #suite.addTest(unittest.makeSuite(call_spots.TestColorNormalisation, 'test'))
    return suite


def suite_all():
    suite = suite_utils()
    suite.addTest(suite_setup())
    suite.addTest(suite_extract())
    suite.addTest(suite_find_spots())
    suite.addTest(suite_stitch())
    suite.addTest(suite_pcr())
    suite.addTest(suite_call_spots())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite_call_spots', exit=True)
    hi = 5
