from .header import Header
import astropy.io.fits as pyfits
import numpy
from scipy import ndimage
from scipy import __version__ as scipyversion
from scipy.interpolate import interp1d


class Data(Header):
    """A class which contains the processes for handling spectral data which
    is common for handling 1D, 2D and 3D spectra.

     Parameters
     ----------
     data : `numpy.ndarray`, optional
        A 1D, 2D, or a 3D numpy array containing all the data. The elements
        of a 1D array follows the wavelength elements. A 2D array should be
        structured such that the different spectra or located along the
        first dimension. For a 3D array, the different spectra are
        distributed along the second and third dimension.
    wave : `numpy.ndarray`, optional
        The wavelength at each point of the `data` array.
    error : `numpy.ndarray`, optional
        The error spectrum, should be of the same shape as `data`.
        If `error` equals None, it is assumed the error spectrum is not
        known.
    mask : `numpy.ndarray`, optional
        A boolean array where True represents a masked (invalid) data point
        and False a good data point. Should be of the same shape as `data`.
    error_weight : `numpy.ndarray`, optional
        Unused at the current moment?
    normalization : `numpy.ndarray`, optional
        An array which is used to normalize the data/error; both data and
        error are divided by `normalization`. Should be of the same shape
        as `data`.
    inst_fwhm : float, optional
        The instrumental FWHM in the same units as `wavelength`.
    header : Header, optional
        Contains information for reading and writing data to and from Fits
        files.
    """
    def __init__(self, data=None, wave=None, error=None, mask=None, error_weight=None, normalization=None, inst_fwhm=None,
    header=None):
        Header.__init__(self, header=header)
        self._data = data
        if data is not None:
            self._dim = data.shape
            if len(data.shape) == 3:
                self._datatype = "CUBE"
                self._res_elements = data.shape[0]
                self._dim_y = data.shape[1]
                self._dim_x = data.shape[2]
            elif len(data.shape) == 2:
                self._datatype = "RSS"
                self._res_elements = data.shape[1]
                self._fibers = data.shape[0]
            elif len(data.shape) == 1:
                self._datatype = "Spectrum1D"
                self._pixels = numpy.arange(self._dim[0])

        self._wave = wave

        self._error = error

        self._error_weight = error_weight

        self._mask = mask

        self._normalization = normalization

        self._inst_fwhm = inst_fwhm

    def getWave(self):
        """Obtain the wavelength grid as a 1D numpy array."""
        return self._wave

    def getWaveStep(self):
        """Obtain the step in the wavelength grid, assumption is that the
        wavelength grid is linear."""
        return numpy.min(self._wave[1:] - self._wave[:-1])

    def getShape(self):
        """Obtain the shape of the data."""
        return self._dim

    def getData(self):
        """Obtain the data as a numpy array."""
        return self._data

    def setData(self, data):
        """Set the data by providing a numpy array. The array should
        be matching the shape of the wavelength grid along the corresponding
        axis for Spectrum1D, RSS and Cube data."""
        self._data = data

    def getError(self):
        """Obtain the error associated to the data as a numpy array."""
        return self._error

    def setError(self, error):
        """Set the error by providing a numpy array. The array should be of the
        same shape as the data."""
        self._error = error

    def getMask(self):
        """Obtain the mask as a numpy array."""
        return self._mask

    def setMask(self, mask):
        """Set the mask by providing a numpy array. The mask should be of
        the same shape as the data."""
        self._mask = mask

    def getFWHM(self):
        """Obtain the FWHM of the data, provided in the same units as the
        wavelength grid."""
        return self._inst_fwhm

    def setFWHM(self, FWHM):
        """Set the value of the FWHM of the data."""
        self._inst_fwhm = FWHM

    def getNormalization(self):
        """Obtain the normalization of the spectrum as a numpy array."""
        return self._normalization

    def setNormalization(self, normalization):
        """Set the normalization of the spectrum by providing a numpy array.
           The array should be of the same shape as the data."""
        self._normalization = normalization

    def correctError(self, replace_error=1e10):
        """Corrects any negative value in `error` to `replace_error`."""
        if self._error is not None:
            select = (self._error <= 0.0)
            if self._mask is not None:
                self._mask[select] = True
            self._error[select] = replace_error

    def subWaveMask(self, select_wave):
        """Obtain a copy of Spectrum1D within a certain wavelength range by
        supplying an index array for obtaining the wanted wavelengths.

        Parameters
        ----------
        select_wave : numpy.ndarray
            A 1D boolean array where the True value represents which elements
            in the `wave`, `data`, `error`, `mask` and `normalization`

        Returns
        -------
        spec : Spectrum1D
            A new `Spectrum1D` instance containing only the elements
            according to `select_wave`.
        """

        [new_error, new_mask, new_fwhm, new_normalization] = [None, None, None, None]

        new_wave = self._wave[select_wave]
        if self._datatype == "Spectrum1D":
            slicer = numpy.s_[select_wave]
        elif self._datatype == "RSS":
            slicer = numpy.s_[:, select_wave]
        elif self._datatype == "CUBE":
            slicer = numpy.s_[select_wave, :, :]
        new_data = self._data[slicer]
        if self._inst_fwhm is not None:
            new_fwhm = self._inst_fwhm[slicer]
        if self._error is not None:
            new_error = self._error[slicer]
        if self._mask is not None:
            new_mask = self._mask[slicer]
        if self.getNormalization() is not None:
            new_normalization = self._normalization[slicer]

        data_out = Data(wave=new_wave, data=new_data, error=new_error, mask=new_mask,
                        normalization=new_normalization, inst_fwhm=new_fwhm)
        data_out.__class__ = self.__class__
        return data_out

    def subWaveLimits(self, wave_start=None, wave_end=None):
        """Obtain a copy of Spectrum1D within a certain wavelength range.

        Parameters
        ----------
        wave_start : float, optional
            The lower limit for the output `Data`.
        wave_end : float, optional
            The upper limit for the output `Data`.

        Returns
        -------
        data_out : `Data`
            The output object where the wavelength cut is applied to.
        """
        select = numpy.ones(len(self.getWave()), dtype='bool')
        if wave_start is not None:
            select[self.getWave() < wave_start] = False
        if wave_end is not None:
            select[self.getWave() > wave_end] = False
        data_out = self.subWaveMask(select)
        return data_out

    def normalizeSpec(self, pixel_width, mask_norm=None):
        """Normalize the spectrum by applying a running mean filter to the data.

        Parameters
        ----------
        pixel_width : int
            The length of the running mean filter window.
        mask_norm : numpy.ndarray
            The 1D boolean numpy array which is added to the mask which is
            already in place for the normalization process.

        Returns
        -------
        data_out : `Data`
            A new instance where the normalization is applied to.
        """

        temp_data = numpy.array(self._data)
        axis = 0 if self._datatype == 'CUBE' else -1
        if mask_norm is not None:
            indices = numpy.indices(self.getWave().shape)[0]
            mask_idx = indices[~mask_norm]
            if self._datatype == 'RSS':
                slicer = numpy.s_[:, ~mask_norm]
                left = self._data[:, mask_idx[0]].flatten()
                right = self._data[:, mask_idx[-1]].flatten()
            elif self._datatype == 'CUBE':
                slicer = numpy.s_[~mask_norm, :, :]
                left = self._data[mask_idx[0], :, :].flatten()
                right = self._data[mask_idx[-1], :, :].flatten()
            elif self._datatype == 'Spectrum1D':
                slicer = numpy.s_[~mask_norm]
                left = self._data[mask_idx[0]]
                right = self._data[mask_idx[-1]]
        if pixel_width == 0:
            temp_data /= numpy.mean(self._data[slicer], axis=axis)
        else:
            if mask_norm is not None:
                if scipyversion < "0.17":
                    edges = numpy.r_[left * numpy.ones((mask_idx[0] - indices[0], 1)),
                                     right * numpy.ones((indices[-1] - mask_idx[-1], 1))]
                    if edges.size == 0:
                        edges = numpy.nan
                    interp = interp1d(mask_idx, self._data[slicer], axis=axis, bounds_error=False, fill_value=edges)
                else:
                    interp = interp1d(mask_idx, self._data[slicer], axis=axis, bounds_error=False,
                                      fill_value='extrapolate')
                temp_data = interp(indices)

            mean = ndimage.filters.convolve1d(temp_data, numpy.ones(pixel_width) / pixel_width, axis=axis,
                                              mode='nearest')

        select_zero = mean == 0
        mean[select_zero] = 1
        new_data = self._data / mean
        new_error = self._error / numpy.fabs(mean) if self._error is not None else None

        data_out = Data(wave=self._wave, data=new_data, error=new_error, mask=self._mask, normalization=mean,
                        inst_fwhm=self._inst_fwhm)
        data_out.__class__ = self.__class__
        return data_out

    def unnormalizedSpec(self):
        """Remove the normalization from the spectrum.

        Returns
        -------
        data_out : `Data`
            A new instance where the normalization is removed from.
        """
        data = self._data * self._normalization
        if self._error is not None:
            error = self._error * numpy.fabs(self._normalization)
        else:
            error = None
        data_out = Data(wave=self._wave, data=data, error=error, mask=self._mask, normalization=None,
                        inst_fwhm=self._inst_fwhm)
        data_out.__class__ = self.__class__
        return data_out

    def applyNormalization(self, normalization):
        """Apply the normalization to the data and the errors."""
        if self._normalization is None:
            self._data = self._data / normalization
            if self._error is not None:
                self._error = self._error / numpy.fabs(normalization)

    def setVelSampling(self, vel_sampling):
        """Change the velocity sampling of the spectra (float, km/s)."""
        self._vel_sampling = vel_sampling

    def getVelSampling(self):
        """Obtain the velocity sampling of the spectra in km/s."""
        return self._vel_sampling

    def loadFitsData(self, filename, extension_data=None, extension_mask=None, extension_error=None,
                     extension_errorweight=None, extension_hdr=0):
        """
            Load data from a FITS image into a Data object

            Parameters
            --------------
            filename : string
                Name or Path of the FITS image from which the data shall be loaded

            extension_data : int or string, optional with default: None
                Number or name of the FITS extension containing the data

            extension_mask : int or string, optional with default: None
                Number or name of the FITS extension containing the masked pixels

            extension_error : int or string, optional with default: None
                Number or string of the FITS extension containing the errors for the values

            extension_errorweight : int or string, optional with default: None
                Number or string of the FITS extension containing the errorweights that are only present in data
                consisting of oversampled spatial information.

            extension_hdr : int or string, optional with default: None
                Number or name of the FITS extension containing the fits header to be used for the cube information like
                wavelength or WCS system.
        """
        hdu = pyfits.open(filename)
        self._dim = None
        if extension_data is None and extension_mask is None and extension_error is None and \
                extension_errorweight is None:
            if hdu[0].data is not None:
                self._data = hdu[0].data
                self._dim = self._data.shape
                self.setHeader(header=hdu[extension_hdr].header, origin=filename)
                try:
                    self.getHdrValue('ARRAY1')
                    for i in range(self._dim[0]):
                        try:
                            array = self.getHdrValue('ARRAY%d' % (i + 1)).replace(' ', '')
                            if array == 'SPECTRUM' or array == 'DATA':
                                self._data = hdu[0].data[i, :]
                                self._dim = self._data.shape
                            elif array == 'ERROR':
                                self._error = hdu[0].data[i, :]
                            elif array == 'WAVE':
                                self._wave = hdu[0].data[i, :]
                            elif array == 'MASK':
                                self._mask = (hdu[0].data[i, :] >= 1.0)
                        except KeyError:
                            pass

                    if self._wave is None:
                        try:
                            wave = (numpy.arange(self._dim[0]) - (self.getHdrValue('CRPIX1') - 1)) * \
                                   self.getHdrValue('CD1_1') + self.getHdrValue('CRVAL1')
                        except KeyError:
                            wave = (numpy.arange(self._dim[0]) - (self.getHdrValue('CRPIX1') - 1)) * \
                                   self.getHdrValue('CDELT1') + self.getHdrValue('CRVAL1')
                        else:
                            pass

                        DC_flag = self.getHdrValue('DC-FLAG')
                        if int(DC_flag) == 1:
                            self._wave = 10**wave
                        else:
                            self._wave = wave
                except KeyError:
                    if len(hdu) > 1:
                        for i in range(1, len(hdu)):
                            if hdu[i].header['EXTNAME'].split()[0] == 'ERROR':
                                self._error = hdu[i].data
                            elif hdu[i].header['EXTNAME'].split()[0] == 'WAVE':
                                self._wave = hdu[i].data
                            elif hdu[i].header['EXTNAME'].split()[0] == 'BADPIX':
                                self._mask = hdu[i].data.astype('bool')
            elif not hdu[1].is_image:
                tab = hdu[1].data
                try:
                    self._wave = 10**tab['loglam']
                except KeyError:
                    self._wave = tab['lambda']
                try:
                    self._data = tab['flux']
                except KeyError:
                    self._data = tab['data']
                try:
                    self._error = numpy.sqrt(tab['ivar'])
                except KeyError:
                    try:
                        self._error = tab['error']
                    except KeyError:
                        pass
                try:
                    self._mask = tab['and_mask'] != 0
                except KeyError:
                    try:
                        self._mask = tab['mask'] != 0
                    except KeyError:
                        pass
                self._dim = self._data.shape
        else:
            self.setHeader(header=hdu[extension_hdr].header, origin=filename)
            if extension_data is not None:
                self._data = hdu[extension_data].data
                self._dim = self._data.shape
            if extension_mask is not None:
                self._mask = hdu[extension_mask].data
                self._dim = self._mask.shape
            if extension_error is not None:
                self._error = hdu[extension_error].data
                self._dim = self._error.shape
            if extension_error is not None:
                self._error_weight = hdu[extension_errorweight].data
                self._dim = self._error_weight.shape
        hdu.close()

        if self._dim is not None:
            if len(self._dim) == 3:
                self._datatype = "CUBE"
                self._res_elements = self._dim[0]
                self._dim_y = self._dim[1]
                self._dim_x = self._dim[2]
                if self._wave is None:
                    self._wave = numpy.arange(self._res_elements) * self.getHdrValue('CDELT3') + \
                                 self.getHdrValue('CRVAL3')
            elif len(self._dim) == 2:
                self._datatype = "RSS"
                self._res_elements = self._dim[1]
                self._fibers = self._dim[0]
                if self._wave is None:
                    self._wave = numpy.arange(self._res_elements) * self.getHdrValue('CDELT1') + \
                                 self.getHdrValue('CRVAL1')
            elif len(self._dim) == 1:
                self._datatype = "Spectrum1D"
                self._pixels = numpy.arange(self._dim[0])
                self._res_elements = self._dim[0]
                if self._wave is None:
                    self._wave = numpy.arange(self._res_elements) * self.getHdrValue('CDELT1') + \
                                 self.getHdrValue('CRVAL1')

        if extension_hdr is not None:
            self.setHeader(hdu[extension_hdr].header, origin=filename)

    def loadTxtData(self, filename):
        file_in = open(filename)
        lines = file_in.readlines()
        wave = []
        data = []
        error = []
        mask = []
        for i in range(len(lines)):
            if '#' not in lines[i][0]:
                line = lines[i].split()
                wave.append(float(line[0]))
                data.append(float(line[1]))
                try:
                    error.append(float(line[2]))
                except IndexError:
                    error.append(1.0)
                try:
                    mask.append(int(line[3]))
                except IndexError:
                    mask.append(False)
        self._data = numpy.array(data)
        self._dim = self._data.shape
        self._wave = numpy.array(wave)
        if error is not []:
            self._error = numpy.array(error)
        if mask is not []:
            self._mask = numpy.array(mask).astype('bool')
        self._datatype = "Spectrum1D"
        self._pixels = numpy.arange(self._dim[0])
        self._res_elements = self._dim[0]

    def writeFitsData(self, filename, extension_data=None, extension_mask=None, extension_error=None,
                      extension_errorweight=None, extension_normalization=None, store_wave=False):
        """
            Save information of the Data object into a FITS file.
            A single or multiple extension file are possible to create.

            Parameters
            --------------
            filename : string
                Name or Path of the FITS image from which the data shall be loaded

            extension_data : int, optional with default: None
                Number of the FITS extension containing the data

            extension_mask : int, optional with default: None
                Number of the FITS extension containing the masked pixels

            extension_error : int, optional with default: None
                Number of the FITS extension containing the errors for the values
        """
        hdus = [None, None, None, None, None, None]  # create empty list for hdu storage

        # create primary hdus and image hdus
        # data hdu
        if extension_data is None and extension_error is None and extension_mask is None and \
                extension_errorweight is None and extension_normalization is None:
            hdus[0] = pyfits.PrimaryHDU(self._data)
            if self._error is not None:
                hdus[1] = pyfits.ImageHDU(self._error, name='ERROR')
            if self._error_weight is not None:
                hdus[2] = pyfits.ImageHDU(self._error_weight, name='ERRWEIGHT')
            if self._mask is not None:
                hdus[3] = pyfits.ImageHDU(self._mask.astype('uint8'), name='BADPIX')
            if self._normalization is not None:
                hdus[4] = pyfits.ImageHDU(self._normalization, name='NORMALIZE')
        else:
            if extension_data == 0:
                hdus[0] = pyfits.PrimaryHDU(self._data)
            elif extension_data > 0 and extension_data is not None:
                hdus[extension_data] = pyfits.ImageHDU(self._data, name='DATA')

            # mask hdu
            if extension_mask == 0:
                hdu = pyfits.PrimaryHDU(self._mask.astype('uint8'))
            elif extension_mask > 0 and extension_mask is not None:
                hdus[extension_mask] = pyfits.ImageHDU(self._mask.astype('uint8'), name='BADPIX')

            # error hdu
            if extension_error == 0:
                hdu = pyfits.PrimaryHDU(self._error)
            elif extension_error > 0 and extension_error is not None:
                hdus[extension_error] = pyfits.ImageHDU(self._error, name='ERROR')

            if extension_errorweight == 0:
                hdu = pyfits.PrimaryHDU(self._error_weight)
            elif extension_errorweight > 0 and extension_errorweight is not None:
                hdus[extension_errorweight] = pyfits.ImageHDU(self._error_weight, name='ERRWEIGHT')

            if extension_normalization == 0:
                hdu = pyfits.PrimaryHDU(self._normalization)
            elif extension_normalization > 0 and extension_normalization is not None:
                hdus[extension_normalization] = pyfits.ImageHDU(self._normalization, name='NORMALIZE')
        if store_wave:
            hdus[-1] = pyfits.ImageHDU(self._wave,  name='WAVE')

        # remove not used hdus
        for i in range(len(hdus)):
            try:
                hdus.remove(None)
            except:
                break

        if len(hdus) > 0:
            hdu = pyfits.HDUList(hdus)  # create an HDUList object
            if self._header is not None and not store_wave:
                if self._wave is not None:
                    if self._datatype == 'CUBE':
                        self.setHdrValue('CRVAL3', self._wave[0])
                        self.setHdrValue('CDELT3', (self._wave[1] - self._wave[0]))
                    else:
                        self.setHdrValue('CRVAL1', self._wave[0])
                        self.setHdrValue('CDELT1', (self._wave[1] - self._wave[0]))
                hdu[0].header = self.getHeader()  # add the primary header to the HDU
                hdu[0].update_header()
            else:
                if self._wave is not None and not store_wave:
                    if self._datatype == 'CUBE':
                        try:
                            hdu[0].header.update('CRVAL3', self._wave[0])
                        except:
                            hdu[0].header['CRVAL3'] = (self._wave[0])
                        try:
                            hdu[0].header.update('CDELT3', self._wave[1] - self._wave[0])
                        except:
                            hdu[0].header['CDELT3'] = (self._wave[1] - self._wave[0])
                    else:
                        try:
                            hdu[0].header.update('CRVAL1', self._wave[0])
                        except:
                            hdu[0].header['CRVAL1'] = (self._wave[0])
                        try:
                            hdu[0].header.update('CDELT1', self._wave[1] - self._wave[0])
                        except:
                            hdu[0].header['CDELT1'] = (self._wave[1] - self._wave[0])
        hdu.writeto(filename, overwrite=True)  # write FITS file to disc
