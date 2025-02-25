import numpy
from .fit_profile import fit_linearComb
from .data import Data
from scipy import ndimage
from scipy import interpolate
try:
    import emcee
except ImportError:
    emcee = None
try:
    import pymc
except ImportError:
    pymc = None

from copy import deepcopy
try:
    import copy_reg
except ImportError:
    import copyreg as copy_reg
from types import *
from sys import version_info


class Spectrum1D(Data):
    """A class representing 1D spectrum.

    `Spectrum1D` is a subclass of Data which allows for handling and
    organizing a one- dimensional spectrum. The class supports reading and
    writing FITS files, resampling and rebinning, velocity shifting and
    broadening, the application of extinction corrections and various
    advanced fitting functions.

    Parameters
    ----------
    wave : `numpy.ndarray`
        The wavelength at each point of the `data` array.
    data : `numpy.ndarray`
        The spectrum. Should be of the same size as `wave`.
    error : `numpy.ndarray`, optional
        The error spectrum.
        If `error` equals None, it is assumed the error spectrum is not
        known.
    mask : `numpy.ndarray`
        A boolean array where True represents a masked (invalid) data point
        and False a good data point.
    normalization : `numpy.ndarray`
        An array which is used to normalize the data/error; both data and
        error are divided by `normalization`.
    inst_fwhm : float
        The instrumental FWHM in the same units as `wavelength`.
    header : Header, optional
        Contains information for reading and writing data to and from Fits
        files.
    """
    def __init__(self, wave=None, data=None, error=None, mask=None, normalization=None, inst_fwhm=None, header=None):
        Data.__init__(self, wave=wave, data=data, error=error, mask=mask, normalization=normalization,
                      inst_fwhm=inst_fwhm, header=header)

    def hasData(self, start_wave=None, end_wave=None):
        """Check if there is any unmasked data available between the provided
        wavelength limits.

        Parameters
        ----------
        start_wave : float, optional
            The lower wavelength limit. The standard value is the lowest value
            in the wavelength grid.
        end_wave : float, optional
            The upper wavelength limit. The standard value is the lowest value
            in the wavelength grid.

        Returns
        -------
        dataAvailable : bool
            True if there is unmasked data with the wavelength limits, otherwise
            False.
        """
        if start_wave is not None:
            self._mask = numpy.logical_or(self._mask, self._wave < start_wave)
        if end_wave is not None:
            self._mask = numpy.logical_or(self._mask, self._wave > end_wave)

        if numpy.sum(self._data) != 0 and numpy.sum(self._mask) != len(self._data):
            return True
        else:
            return False

    def resampleSpec(self, ref_wave, method='spline', err_sim=500, replace_error=1e10):
        """Returns a new Spectrum1D object resampled to a new wavelength grid

        The interpolation is perfomed based on the `method`-argument.

        Parameters
        ----------
        ref_wave : numpy.ndarray
            The new wavelength array to which the spectrum will be
            resampled.
        method : {'spline', 'linear', 'hann', 'lanczos2', 'lanczos3'}, optional
            Specifies the resampling method.
            'spline' : 3rd degree spline interpolation without smoothing
            'linear' : linear interpolation
            'hann' : *Not implemented*, uses a Hann window for resampling
            'lanczos2' : *Not implemented*, uses a Lanczos kernel for
            resampling with the window parameter set at a = 2.
            'lanczos3' : *Not implemented*, uses a Lanczos kernel for
            resampling with the window parameter set at a = 3. It is
            therefore broader than `lanczos2`-kernel.
        err_sim : *Not implemented* int
        replace_error : *Not implemented* int

        Returns
        -------
        spec : Spectrum1D
            A new `Spectrum1D` instance resampled to the new wavelength grid.
            Currently, the masks, errors and normalization are not
            propagated in `spec`.
        """
        # perform the interpolation on the data
        if method == 'spline':
            intp = interpolate.UnivariateSpline(self._wave, self._data, s=0, k=3)
            new_data = intp(ref_wave)
        elif method == 'linear':
            intp = interpolate.UnivariateSpline(self._wave, self._data, s=0, k=1)
            new_data = intp(ref_wave)
#           elif method=='hann':

#            elif method=='lanczos2':

#            elif method=='lanczos3':

#        if self._error is not None and err_sim>0:
#            sim  = numpy.zeros((err_sim, len(ref_wave)), dtype=numpy.float32)
#            data = numpy.zeros(len(self._wave), dtype=numpy.float32)
#            numpy.random.seed()
#            for i in range(err_sim):
#                data = numpy.random.normal(self._data, self._error).astype(numpy.float32)
#                if method=='spline':
#                    intp = interpolate.UnivariateSpline(self._wave, data, s=0)
#                    out =intp(ref_wave)
#                elif method=='linear':
#                    intp = interpolate.UnivariateSpline(self._wave, data, k=1, s=0)
#                    out = intp(ref_wave)
#
#                sim[i, :] = out
#            new_error = numpy.std(sim, 0)
#
#
#        elif self._error is None or err_sim==0:
#            new_error=None
        spec_out = Spectrum1D(wave=ref_wave, data=new_data)
        return spec_out

    def rebinLogarithmic(self, oversampling=2):
        """Rebin the spectrum from a linear wavelength grid to a logarithmic
        wavelength grid.

        Returns
        -------
        spec : Spectrum1D
            A new Spectrum1D object with the `data` in logarithmic base.
        """
        wave_log = numpy.logspace(numpy.log10(self._wave[0]),
                                  numpy.log10(self._wave[-1]),
                                  len(self._wave) * oversampling)
        new_spec = self.resampleSpec(wave_log)
        new_spec.setVelSampling((self._wave[1] - self._wave[0]) / self._wave[0] * 300000.0)
        return new_spec

    def applyGaussianLOSVD(self, vel, disp_vel):
        """Returns a broadened copy of the spectrum.

        Parameters
        ----------
        vel : float
            The `wave` is redshifted according to `vel`, which should
            be specified in km/s.
        disp_vel : float
            The velocity dispersion value in km/s, which will be used
            for the Gaussian broadening of the data.

        Returns
        -------
        spec : Spectrum1D
            A new Spectrum1D object which is redshifted and broadened.

        Notes
        -----
        No correction is applied to `error`, `mask`, and
        `normalization`.
        """
        disp_pix = disp_vel / self._vel_sampling
        new_data = ndimage.filters.gaussian_filter(self._data, disp_pix, mode='constant')
        wave = self._wave * (1 + vel / 300000.0)
        spec_out = Spectrum1D(wave=wave, data=new_data, error=None)
        try:
            spec_out._vel_sampling = self._vel_sampling
        except:
            pass
        return spec_out

    def correctExtinction(self, A_V, mode='correct', law='Cardelli', R_V=3.1):
        """
        Parameters
        ----------
        A_V :
        mode :
        Cardelli :
        R_V :

        Returns :
        spec_out :
        """
        micron = self._wave / 10000.0
        wave_number = 1.0 / micron
        y = wave_number - 1.82
        ax = 1 + (0.17699 * y) - (0.50447 * y ** 2) - (0.02427 * y ** 3) + (0.72085 * y ** 4) + (0.01979 * y ** 5)\
            - (0.77530 * y ** 6) + (0.32999 * y ** 7)
        bx = (1.41338 * y) + (2.28305 * y ** 2) + (1.07233 * y ** 3) - (5.38434 * y ** 4) - (0.62251 * y ** 5)\
            + (5.30260 * y ** 6) - (2.09002 * y ** 7)
        Arat = ax + (bx / R_V)
        Alambda = Arat * A_V
        cor_factor = 10 ** (Alambda / -2.5)
        if mode == 'correct':
            data = self._data / cor_factor
            if self._error is not None:
                error = self._error / cor_factor
            else:
                error = None
        elif mode == 'apply':
            data = self._data * cor_factor
            if self._error is not None:
                error = self._error * cor_factor
            else:
                error = None
        spec_out = Spectrum1D(data=data, wave=self._wave, error=error)
        try:
            spec_out._vel_sampling = self._vel_sampling
        except:
            pass
        return spec_out

    def randomizeSpectrum(self):
        """Draw a new spectrum by assuming that the `error` corresponding
        to `data` follows a normal distribution.

        Returns
        -------
        spec_out : Spectrum1D
            A new Spectrum1D object representing the new spectrum.

        Notes
        -----
        In the case that the `error` equals None, a copy of the original
        Spectrum1D object is returned.
        """
        numpy.random.seed()
        if self._error is not None:
            data_new = numpy.random.Normal(self._data, self._error)
            spec_out = Spectrum1D(wave=self._wave, data=data_new, error=self._error, mask=self._mask,
                                  inst_fwhm=self._inst_fwhm, normalization=self._normalization, header=self._header)
            try:
                spec_out.setVelSampling(self._vel_sampling)
            except:
                pass
        else:
            spec_out = self
        return spec_out

    def applyKin(self, vel, disp_vel, wave):
        """Shifts and broadens the spectrum and resamples it to a new
        wavelength grid.

        Parameters
        ----------
        vel : float
            The `wave` is redshifted according to `vel`, which should
            be specified in km/s.
        disp_vel : float
            The velocity dispersion value in km/s, which will be used
            for the Gaussian broadening of the data.
        wave : numpy.ndarray
            The new wavelength grid on which the broadened and redshifted
            spectra will be sampled.

        Returns
        -------
        spec : Spectrum1D
            A new Spectrum1D object representing the spectrum after the
            kinematic transformation.
        """
        tempSpec = self.applyGaussianLOSVD(vel, disp_vel)
        tempSpec = tempSpec.resampleSpec(wave)
        return tempSpec

    def fitSuperposition(self, SSPLibrary, nlib_guess=None, vel=None, disp=None, mask_fit=None, negative=False):
        """Fits a superposition of template spectra to the data.

        Parameters
        ----------
        SSPLibrary : SSPlibrary
            Contains a library of template spectra which are used for
            the fitting.
        negative : bool, optional
            When `negative` is False, it will apply non-negative least
            squares to determine the best fit. If `negative` is True,
            ordinary least squares fitting will be applied.

        Returns
        -------
        coeff : numpy.ndarray
            The coefficients of the best fit.
        bestfit_spec : Spectrum1D
            The spectrum which resembles the best combination of
            template spectra.
        chisq : float
            The chi^2 value corresponding to `bestfit_spec`.
        """
        if nlib_guess == 0:
            bestresult = [numpy.inf]
            coeff = None
            for i in range(SSPLibrary.getBaseNumber()):
                select = numpy.zeros(SSPLibrary.getBaseNumber(), dtype=bool)
                select[i] = True
                lib = SSPLibrary.subLibrary(select)
                result = self.fitSuperposition(lib, 1, vel, disp, mask_fit, negative)
                if result[-1] < bestresult[-1]:
                    bestresult = result
                    coeff = select
            return coeff, bestresult[1], bestresult[2]
        if self._error is None:
            error = numpy.ones(self._dim, dtype=numpy.float32)
        else:
            error = self._error
        if mask_fit is not None and self.getMask() is not None:
            self.setMask(numpy.logical_or(self.getMask(), mask_fit))
        elif mask_fit is not None:
            self.setMask(mask_fit)
        if self._mask.sum() == self._mask.size:
            raise ValueError('No data points in spectrum left for fitting.')

        if vel is not None and disp is not None:
            SSPLibrary = SSPLibrary.applyGaussianLOSVD(vel, disp)
        if len(SSPLibrary.getWave()) != len(self._wave) or numpy.sum(SSPLibrary.getWave() - self._wave) != 0.0:
            tempLib = SSPLibrary.resampleBase(self._wave)
        else:
            tempLib = SSPLibrary
        if SSPLibrary.getBaseNumber() == 1:
            libFit = fit_linearComb(tempLib.getBase(), coeff=numpy.array([1], dtype=numpy.float32))
        else:
            libFit = fit_linearComb(tempLib.getBase())
            libFit.fit(self._data, error, self._mask, negative=negative)
        bestfit_spec = Spectrum1D(self._wave, data=libFit(), normalization=self.getNormalization(), mask=self.getMask())
        chi2 = libFit.chisq(self._data, sigma=error, mask=self._mask)
        return libFit.getCoeff(), bestfit_spec, chi2

    def fitKinMCMC_fixedpop(self, spec_model, vel_min, vel_max, vel_disp_min, vel_disp_max, mcmc_code='emcee',
                            walkers=50, burn=1000, samples=3000, thin=2):
        """Fits a spectrum according to Markov chain Monte Carlo
        algorithm to obtain statistics on the kinematics. This uses the
        PyMC library.

        Parameters
        ----------
        spec_model : Spectrum1D
            A single spectrum from a SSP library used to fit the data of the
            current spectrum with.
        vel_min : float
            The minimum velocity in km/s used in the MCMC.
        vel_max : float
            The maximum velocity in km/s used in the MCMC.
        vel_disp_min : float
            The minimum velocity dispersion in km/s used in the MCMC.
        vel_disp_max : float
            The maximum velocity dispersion in km/s used in the MCMC.
        burn : int, optional
            The burn-in parameter that is often applied in MCMC
            implementations. The first `burn` samples will be discarded
            in the further analysis.
        samples : int, optional
            The number of iterations runned by PyMC.
        thin : int, optional
            Only keeps every `thin`th sample, this argument should
            circumvent any possible autocorrelation among the samples.

        Returns
        -------
        M : pymc.MCMC
            Contains all the relevant information from the PyMC-run.
        """
        valid_pix = numpy.logical_not(self._mask)
        if mcmc_code == 'pymc':
            vel = pymc.Uniform('vel', lower=vel_min, upper=vel_max)
            disp = pymc.Uniform('disp', lower=vel_disp_min, upper=vel_disp_max)

            @pymc.deterministic(plot=False)
            def m(vel=vel, disp=disp):
                return spec_model.applyKin(vel, disp, self._wave).getData()[
                    valid_pix]

            d = pymc.Normal('d', mu=m, tau=self._error[valid_pix] ** (-2),
                            value=self._data[valid_pix], observed=True)
            m = pymc.MCMC([vel, disp, m, d])
            m.use_step_method(pymc.AdaptiveMetropolis, [vel, disp])
            for i in range(walkers):
                m.sample(samples, burn, thin, progress_bar=False)
            return m

        ndim = 2

        def log_prior(theta):
            vel, disp = theta
            if vel_min < vel < vel_max and vel_disp_min < disp < vel_disp_max:
                return 0.0
            return -numpy.inf

        def log_likelihood(theta, x, y, e):
            vel, disp = theta
            y_model = spec_model.applyKin(vel, disp, x).getData()[valid_pix]
            inv_sigma2 = 1.0 / (e[valid_pix] ** 2)
            return -0.5 * numpy.sum((y[valid_pix] - y_model) ** 2 * inv_sigma2 - numpy.log(inv_sigma2))

        def log_posterior(theta, x, y, e):
            return log_prior(theta) + log_likelihood(theta, x, y, e)

        guess = numpy.c_[numpy.random.uniform(vel_min, vel_max, walkers),
                         numpy.random.uniform(vel_disp_min, vel_disp_max, walkers)]
        sampler = emcee.EnsembleSampler(walkers, ndim, log_posterior,
                                        args=(self.getWave(), self.getData(),
                                              self.getError()))
        sampler.run_mcmc(guess, samples, thin=thin)
        trace = sampler.chain[:, burn // thin:, :].T

        return trace

    def fit_Kin_Lib_simple(self, lib_SSP, nlib_guess, vel_min, vel_max, disp_min, disp_max, mask_fit=None, iterations=3,
                           mcmc_code='emcee', walkers=50, burn=50, samples=200, thin=1, sample_out=False):
        """Fits template spectra according to Markov chain Monte Carlo
        algorithm. This uses the PyMC library.

        Parameters
        ----------
        lib_SSP : SSPlibrary
            The library containing the template spectra.
        nlib_guess : int
            The initial guess for the best fitting template spectrum.
        vel_min : float
            The minimum velocity in km/s used in the MCMC.
        vel_max : float
            The maximum velocity in km/s used in the MCMC.
        disp_min : float
            The minimum velocity dispersion in km/s used in the MCMC.
        disp_max : float
            The maximum velocity dispersion in km/s used in the MCMC.
        mask_fit : `numpy.ndarray`
            A boolean array representing any wavelength regions which are masked
            out during the fitting.
        iterations : int
            The number of iterations applied to determine the best combination of
            velocity, velocity dispersion and the coefficients for the set of
            template spectra.
        burn : int, optional
            The burn-in parameter that is often applied in MCMC implementations.
            The first `burn` samples will be discarded in the further analysis.
        samples : int, optional
            The number of iterations runned by PyMC.
        thin : int, optional
            Only keeps every `thin`th sample, this argument should circumvent
            any possible autocorrelation among the samples.

        Returns
        -------
        vel : float
            The average velocity from the MCMC-sample.
        vel_err : float
            The standard deviation in the velocity from the MCMC-sample.
        disp : float
            The average velocity dispersion from the MCMC-sample.
        disp_err : float
            The standard devation in the velocity dispersion from the
            MCMC-sample.
        bestfit_spec : Spectrum1D
            The best fitted spectrum obtained from the linear
            combination of template spectra.
        coeff : numpy.ndarray
            The coefficients of the SSP library which will produce the best fit
            to the data.
        chisq : float
            The chi^2 value between `bestfit_spec` and `data`.
        """
        # The case that the spectrum is fitted to each SSP
        if nlib_guess == 0:
            bestresult = [numpy.inf]
            coeff = None
            for i in range(lib_SSP.getBaseNumber()):
                select = numpy.zeros(lib_SSP.getBaseNumber(), dtype=bool)
                select[i] = True
                lib = lib_SSP.subLibrary(select)
                result = self.fit_Kin_Lib_simple(lib, 1, vel_min, vel_max, disp_min, disp_max, mask_fit,
                                                 iterations, burn, samples, thin)
                if result[-1] < bestresult[-1]:
                    bestresult = result
                    coeff = select
            vel, vel_err, Rvel, disp, disp_err, Rdisp, bestfit_spec, trash, chi2 = bestresult
            return vel, vel_err, Rvel, disp, disp_err, Rdisp, bestfit_spec, coeff, chi2
        elif 0 < nlib_guess <= lib_SSP.getBaseNumber():
            spec_lib_guess = lib_SSP.getSpec(nlib_guess)
        else:
            spec_lib_guess = lib_SSP.getSpec(1)
        mask_init = deepcopy(self.getMask())
        if mask_fit is not None:
            excl_fit_init = mask_fit.maskPixelsObserved(self.getWave(), ((vel_min+vel_max)/2.0) / 300000.0)
            if mask_init is not None:
                self.setMask(numpy.logical_or(mask_init, excl_fit_init))
            else:
                self.setMask(excl_fit_init)
        for i in range(iterations):
            w = walkers
            if mcmc_code == 'pymc' and i != iterations - 1:
                w = 1
            m = self.fitKinMCMC_fixedpop(spec_lib_guess, vel_min, vel_max,
                                         disp_min, disp_max, mcmc_code, w,
                                         burn, samples, thin)
            if mcmc_code == 'pymc':
                trace_vel = m.trace('vel', chain=None)[:]
                trace_disp = m.trace('disp', chain=None)[:]
            else:
                trace_vel, trace_disp = m
            vel = numpy.mean(trace_vel)
            vel_err = numpy.std(trace_vel)
            disp = numpy.mean(trace_disp)
            disp_err = numpy.std(trace_disp)
            lib_vel = lib_SSP.applyGaussianLOSVD(vel, disp)
            (coeff, bestfit_spec, chi2) = self.fitSuperposition(lib_vel)
            if nlib_guess < 0:
                break
            spec_lib_guess = lib_SSP.compositeSpectrum(coeff)
            if mask_fit is not None:
                excl_fit = mask_fit.maskPixelsObserved(self.getWave(), vel / 300000.0)
                if mask_init is not None:
                    self.setMask(numpy.logical_or(mask_init, excl_fit))
                else:
                    self.setMask(excl_fit)

        if mcmc_code == 'pymc':
            if walkers > 2:
                gelman_rubin = pymc.gelman_rubin(m)
                Rvel = gelman_rubin['vel']
                Rdisp = gelman_rubin['disp']
            else:
                Rvel = 0
                Rdisp = 0
        else:
            n = float(trace_vel.shape[0])

            Bvel = n * numpy.var(trace_vel.mean(axis=0), ddof=1)
            Wvel = numpy.mean(numpy.var(trace_vel, axis=0, ddof=1))
            Rvel = numpy.sqrt(1 - 1 / n + Bvel / n / Wvel)

            Bdisp = n * numpy.var(trace_disp.mean(axis=0), ddof=1)
            Wdisp = numpy.mean(numpy.var(trace_disp, axis=0, ddof=1))
            Rdisp = numpy.sqrt(1 - 1 / n + Bdisp / n / Wdisp)
        
        if not sample_out:
            return vel, vel_err, Rvel, disp, disp_err, Rdisp, bestfit_spec, coeff, chi2, None, None
        else:
            return vel, vel_err, Rvel, disp, disp_err, Rdisp, bestfit_spec, coeff, chi2, trace_vel, trace_disp

    def fit_Lib_Boots(self, lib_SSP, vel, disp, vel_err=None, disp_err=None, par_eline=None, select_wave_eline=None,
                      mask_fit=None, method_eline='leastsq', guess_window=10.0, spectral_res=0.0, ftol=1e-4, xtol=1e-4,
                      bootstraps=100, modkeep=80, parallel=1, plot=False):
        """

        Parameters
        ----------
        lib_SSP : SSPlibrary
            The library containing the template spectra.
        vel : float
            The redshift of the object in km/s.
        disp : float
            The velocity dispersion value in km/s, which will be used
            for the Gaussian broadening of the template spectra.
        vel_err : float, optional
            ???Unused???
        disp_err : float, optional
            ???Unused???
        par_eline : parFile, optional
            A list of emission lines that will be included in the bootstrap
            fitting procedure.
        select_wave_eline : numpy.ndarray
            A 1D boolean array where the True value represents which wavelength
            elements will be used in the emission line fitting.
        method_eline : {'leastsq', 'simplex'}, optional
            This argument specifies if ordinary least squares fitting
            (`leastsq`) should be applied, or if a downhill simplex algorithm
            (`simplex`) should be used.
        guess_window : float, optional
            The wavelength region in which the emission line will be fitted.
        spectral_res : float, optional
            The spectral resolution of the line.
        ftol : float, optional
            The maximum acceptable error for fit convergence.
        xtol : float, optional
            The relative acceptable error for fit convergence.
        bootstraps : int, optional
            The number of bootstraps runs that will be performed.
        modkeep : float
        parallel : {'auto', int}, optional
            If parallel is not equal to one, the python multiprocessing routine
            shall be used to run parts of the code in parallel. With the option
            `auto`, it adjusts the number of parallel processes to the number
            of cpu-cores available.

        Returns
        -------
        """
        numpy.random.seed()
        coeff_full = numpy.zeros((bootstraps, lib_SSP.getBaseNumber()))
        if vel_err is None or disp_err is None:
            kin_SSP = lib_SSP.applyGaussianLOSVD(vel, disp).resampleBase(
                self.getWave())
        line_models = None
        if par_eline is not None:
            line_models = {}
            for n in par_eline._names:
                model = {}
                if par_eline._profile_type[n] == 'Gauss':
                    model['flux'] = numpy.zeros(bootstraps, dtype=numpy.float32)
                    model['vel'] = numpy.zeros(bootstraps, dtype=numpy.float32)
                    model['fwhm'] = numpy.zeros(bootstraps, dtype=numpy.float32)
                line_models[n] = model
        if self._mask is None:
            self._mask = numpy.zeros_like(self._data).astype(bool)
        if mask_fit is not None:
            self.setMask(numpy.logical_or(self.getMask(), mask_fit))
        elif mask_fit is not None:
            self.setMask(mask_fit)
        m = 0
        # try:
        while m < bootstraps:
            if vel_err is not None and disp_err is not None:
                v = numpy.random.normal(vel, vel_err)
                d = numpy.random.normal(disp, disp_err)
                kin_SSP = lib_SSP.applyGaussianLOSVD(v, d).resampleBase(
                    self.getWave())
            (sub_SSPlib, select) = kin_SSP.randomSubLibrary(float(modkeep / 100.0))

            # select_bad = self.getError() <= 0
            # self._error[select_bad] = 1e+10
            # self._mask[select_bad] = True

            spec = Spectrum1D(wave=self.getWave(), data=numpy.random.normal(self.getData(), self.getError()),
                              error=self.getError(), mask=self.getMask(), normalization=self.getNormalization())
            try:
                (coeff, bestfit_spec, chi2) = spec.fitSuperposition(sub_SSPlib)
                factors = numpy.zeros(kin_SSP.getBaseNumber(), dtype=numpy.float32)
                factors[select] = coeff
            except RuntimeError:
                coeff = -1e10
            if numpy.sum(coeff) > -10000:
                coeff_full[m] = factors
                if par_eline is not None:
                    res = Spectrum1D(wave=self.getWave(), data=(spec.getData() - bestfit_spec.getData()),
                                     error=spec.getError(), mask=spec.getMask(),
                                     normalization=self.getNormalization()).unnormalizedSpec()
                    (out_model, best_fit, best_res) = res.fitELines(par_eline, select_wave_eline, method=method_eline,
                                                                    guess_window=guess_window,
                                                                    spectral_res=spectral_res, ftol=ftol,
                                                                    xtol=xtol, parallel=parallel)
                    # if plot and m >= 0 and m < 30:
                    #     print(m)
                    #     print(coeff)
                    #     pylab.plot(res.getWave(), spec.getData(), '-k')
                    #     pylab.plot(res.getWave(), bestfit_spec.getData(), '-r')
                    #     #pylab.plot(res.getWave(),res.getData(),'-k')
                    #     #pylab.plot(res.getWave(),res.getError(),'-r')
                    #     #pylab.plot(res.getWave(),best_fit,'-b')
                    #     pylab.show()
                    for n in par_eline._names:
                        if par_eline._profile_type[n] == 'Gauss':
                            line_models[n]['flux'][m] = out_model[n][0]
                            line_models[n]['vel'][m] = out_model[n][1]
                            line_models[n]['fwhm'][m] = out_model[n][2] * 2.354
                else:
                    line_models = None
                m += 1
            else:
                if line_models is not None:
                    lines_error = {}
                    for n in par_eline._names:
                        error = {}
                        if par_eline._profile_type[n] == 'Gauss':
                            error['flux'] = numpy.nan
                            error['vel'] = numpy.nan
                            error['fwhm'] = numpy.nan
                        lines_error[n] = error
                else:
                    lines_error = None

        if line_models is not None:
            lines_error = {}
            for n in par_eline._names:
                error = {}
                if par_eline._profile_type[n] == 'Gauss':
                    error['flux'] = numpy.std(line_models[n]['flux'])
                    error['vel'] = numpy.std(line_models[n]['vel'])
                    error['fwhm'] = numpy.std(line_models[n]['fwhm'])
                lines_error[n] = error
        else:
            lines_error = None
        return coeff_full, lines_error

    def fitParFile(self, par, err_sim=0, ftol=1e-8, xtol=1e-8, method='leastsq', parallel='auto'):
        """Fits the spectrum and determines the parameters and the corresponding
        errors of the fit.

        Parameters
        ----------
        par : parFile
            The object containing all the constraints on the parameters.
        err_sim : int, optional
            The number of simulations which will be runned to estimate the
            errors.
        ftol : float, optional
            The maximum acceptable error for fit convergence.
        xtol : float, optional
            The relative acceptable error for fit convergence.
        method : {'leastsq', 'simplex'}, optional
            This argument specifies if ordinary least squares fitting
            (`leastsq`) should be applied, or if a downhill simplex algorithm
            (`simplex`) should be used.
        parallel : {'auto', int}, optional
            If parallel is not equal to one, the python multiprocessing routine
            shall be used to run parts of the code in parallel. With the option
            `auto`, it adjusts the number of parallel processes to the number
            of cpu-cores available.
        """
        static_par = deepcopy(par)

        if self.getError() is not None:
            sigma = self.getError()
        else:
            sigma = 1.0
        par.fit(self.getWave(), self.getData(), sigma=sigma, err_sim=err_sim, maxfev=9999, method=method, ftol=ftol,
                xtol=xtol, parallel=parallel)
        par.restoreResult()
        if err_sim > 0 and self._error is not None:
            par_err = deepcopy(static_par)
            par_err._par = par._par_err
            par_err.restoreResult()
            par._parameters_err = par_err._parameters

    def fitELines(self, par, select_wave, method='leastsq', guess_window=0.0, spectral_res=0.0, ftol=1e-4,
                  xtol=1e-4, parallel='auto'):
        """This routine fits a set of emission lines to a spectrum

        Parameters
        ----------
        par : parFile
            The object containing all the constraints on the parameters.
        select_wave : numpy.ndarray
            A 1D boolean array where the True value represents which elements
            in the wave, data, error, mask and normalization.
        method : {'leastsq', 'simplex'}, optional
            This argument specifies if ordinary least squares fitting
            (`leastsq`) should be applied, or if a downhill simplex algorithm
            (`simplex`) should be used.
        guess_window : float, optional
            The wavelength region in which the emission line will be fitted.
        spectral_res : float, optional
            The spectral resolution of the line.
        ftol : float, optional
            The maximum acceptable error for fit convergence.
        xtol : float, optional
            The relative acceptable error for fit convergence.
        parallel : {'auto', int}, optional
            If parallel is not equal to one, the python multiprocessing routine
            shall be used to run parts of the code in parallel. With the option
            `auto`, it adjusts the number of parallel processes to the number
            of cpu-cores available.

        Returns
        -------
        out_model : dictionary
            The flux and the velocity shift of each line
        best_fit : numpy.ndarray
            A 1D numpy array representing the best fitted values at the
            wavelength range `select_wave`.
        best_res : numpy.ndarray
            A 1D numpy array representing the residuals at the wavelength range
            `select_wave`.
        """
        # spec_res = spectral_res.getRes()
        # par = fit_profile.parFile(par_file, spec_res)
        fit_par = deepcopy(par)
        spec_fit = self.subWaveMask(select_wave)
        if guess_window != 0.0:
            fit_par._guess_window = int(guess_window)
            fit_par.guessPar(self.getWave(), self.getData())

        spec_fit.fitParFile(fit_par, err_sim=0, method=method, ftol=ftol, xtol=xtol, parallel=parallel)
        best_fit = fit_par(self.getWave())
        best_res = self.getData() - best_fit
        out_model = {}
        for n in fit_par._names:
            if fit_par._profile_type[n] == 'Gauss':
                out_model[n] = (fit_par._parameters[n]['flux'], fit_par._parameters[n]['vel'],
                                numpy.fabs(fit_par._parameters[n]['disp']) * 2.354)
        return out_model, best_fit, best_res


class SpectralResolution(object):
    def __init__(self, res=None):
        self._res = res
        self._inter = None
        
    def getRes(self, wave):
        if self._inter is None:
            return self._res/2.354
        else:
            return self._inter(wave)/2.354
        
    def compareRes(self, res, wave=None):
        if self._inter is None:
            return res < self.getRes(wave)
        else:
            return numpy.count_nonzero(res > self.getRes(wave)) == 0
    
    def readFile(self, name):
        temp = open(name, 'r')
        lines = temp.readlines()
        wave_res = numpy.zeros(len(lines))
        res = numpy.zeros(len(lines))
        for i in range(len(lines)):
            line = lines[i].split()
            wave_res[i] = float(line[0])
            res[i] = float(line[1])
        self._inter = interpolate.interp1d(wave_res, res)


def loadSpectrum(infile):
    spec = Spectrum1D()
    if '.fits' in infile or '.fit' in infile or '.gz' in infile or '.fz' in infile:
        spec.loadFitsData(infile)
    else:
        spec.loadTxtData(infile)
    return spec


def _pickle_method(method):
    func_name = method.__func__.__name__
    obj = method.__self__
    cls = method.__self__.__class__
    if func_name.startswith('_') and not func_name.endswith('__'):
        cls_name = cls.__name__.lstrip('_')
        if cls_name:
            func_name = '_' + cls_name + func_name
    return _unpickle_method, (func_name, obj, cls)


def _unpickle_method(func_name, obj, cls):
    for cls in cls.mro():
        try:
            func = cls.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)


copy_reg.pickle(MethodType, _pickle_method, _unpickle_method)
