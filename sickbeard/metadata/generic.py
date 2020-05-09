# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
from collections import OrderedDict

import datetime
import io
import os.path
import re

from . import helpers as metadata_helpers
from .. import helpers, logger
from ..indexers import indexer_config
from ..indexers.indexer_config import TVINFO_TVDB
from tvinfo_base.exceptions import *
import sickbeard
# noinspection PyPep8Naming
import encodingKludge as ek
from exceptions_helper import ex
# noinspection PyPep8Naming
from lib import tmdbsimple as TMDB
from lib.fanart.core import Request as fanartRequest
import lib.fanart as fanart
from lxml_etree import etree

from _23 import filter_iter
from six import iteritems, itervalues

# noinspection PyUnreachableCode
if False:
    from typing import Any, AnyStr, Dict, List, Optional, Tuple, Union


class GenericMetadata(object):
    """
    Base class for all metadata providers. Default behavior is meant to mostly
    follow XBMC 12+ metadata standards. Has support for:
    - show metadata file
    - episode metadata file
    - episode thumbnail
    - show fanart
    - show poster
    - show banner
    - season thumbnails (poster)
    - season thumbnails (banner)
    - season all poster
    - season all banner
    """

    def __init__(self,
                 show_metadata=False,  # type: bool
                 episode_metadata=False,  # type: bool
                 use_fanart=False,  # type: bool
                 use_poster=False,  # type: bool
                 use_banner=False,  # type: bool
                 episode_thumbnails=False,  # type: bool
                 season_posters=False,  # type: bool
                 season_banners=False,  # type: bool
                 season_all_poster=False,  # type: bool
                 season_all_banner=False  # type: bool
                 ):

        self.name = "Generic"  # type: AnyStr

        self._ep_nfo_extension = "nfo"  # type: AnyStr
        self._show_metadata_filename = "tvshow.nfo"  # type: AnyStr

        self.fanart_name = "fanart.jpg"  # type: AnyStr
        self.poster_name = "poster.jpg"  # type: AnyStr
        self.banner_name = "banner.jpg"  # type: AnyStr

        self.season_all_poster_name = "season-all-poster.jpg"  # type: AnyStr
        self.season_all_banner_name = "season-all-banner.jpg"  # type: AnyStr

        self.show_metadata = show_metadata
        self.episode_metadata = episode_metadata
        self.fanart = use_fanart
        self.poster = use_poster
        self.banner = use_banner
        self.episode_thumbnails = episode_thumbnails
        self.season_posters = season_posters
        self.season_banners = season_banners
        self.season_all_poster = season_all_poster
        self.season_all_banner = season_all_banner

    def get_config(self):
        # type: (...) -> AnyStr
        config_list = [self.show_metadata, self.episode_metadata, self.fanart, self.poster, self.banner,
                       self.episode_thumbnails, self.season_posters, self.season_banners, self.season_all_poster,
                       self.season_all_banner]
        return '|'.join([str(int(x)) for x in config_list])

    def get_id(self):
        # type: (...) -> AnyStr
        return GenericMetadata.makeID(self.name)

    @staticmethod
    def makeID(name):
        # type: (AnyStr) -> AnyStr
        name_id = re.sub("[+]", "plus", name)
        name_id = re.sub(r"[^\w\d_]", "_", name_id).lower()
        return name_id

    def set_config(self, string):
        # type: (AnyStr) -> None
        config_list = [bool(int(x)) for x in string.split('|')]
        self.show_metadata = config_list[0]
        self.episode_metadata = config_list[1]
        self.fanart = config_list[2]
        self.poster = config_list[3]
        self.banner = config_list[4]
        self.episode_thumbnails = config_list[5]
        self.season_posters = config_list[6]
        self.season_banners = config_list[7]
        self.season_all_poster = config_list[8]
        self.season_all_banner = config_list[9]

    def _has_show_metadata(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_show_file_path(show_obj))
        logger.log(u"Checking if " + self.get_show_file_path(show_obj) + " exists: " + str(result), logger.DEBUG)
        return result

    def has_episode_metadata(self, ep_obj):
        # type: (sickbeard.tv.TVEpisode) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_episode_file_path(ep_obj))
        logger.log(u"Checking if " + self.get_episode_file_path(ep_obj) + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_fanart(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_fanart_path(show_obj))
        logger.log(u"Checking if " + self.get_fanart_path(show_obj) + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_poster(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_poster_path(show_obj))
        logger.log(u"Checking if " + self.get_poster_path(show_obj) + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_banner(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_banner_path(show_obj))
        logger.log(u"Checking if " + self.get_banner_path(show_obj) + " exists: " + str(result), logger.DEBUG)
        return result

    def has_episode_thumb(self, ep_obj):
        # type: (sickbeard.tv.TVEpisode) -> AnyStr
        location = self.get_episode_thumb_path(ep_obj)
        result = None is not location and ek.ek(os.path.isfile, location)
        if location:
            logger.log(u"Checking if " + location + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_season_poster(self, show_obj, season):
        # type: (sickbeard.tv.TVShow,int) -> AnyStr
        location = self.get_season_poster_path(show_obj, season)
        result = None is not location and ek.ek(os.path.isfile, location)
        if location:
            logger.log(u"Checking if " + location + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_season_banner(self, show_obj, season):
        # type: (sickbeard.tv.TVShow,int) -> AnyStr
        location = self.get_season_banner_path(show_obj, season)
        result = None is not location and ek.ek(os.path.isfile, location)
        if location:
            logger.log(u"Checking if " + location + " exists: " + str(result), logger.DEBUG)
        return result

    def _has_season_all_poster(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_season_all_poster_path(show_obj))
        logger.log(u"Checking if " + self.get_season_all_poster_path(show_obj) + " exists: " + str(result),
                   logger.DEBUG)
        return result

    def _has_season_all_banner(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        result = ek.ek(os.path.isfile, self.get_season_all_banner_path(show_obj))
        logger.log(u"Checking if " + self.get_season_all_banner_path(show_obj) + " exists: " + str(result),
                   logger.DEBUG)
        return result

    @staticmethod
    def get_show_year(show_obj, show_info, year_only=True):
        # type: (sickbeard.tv.TVShow, Dict, bool) -> Optional[AnyStr]
        if None is not getattr(show_info, 'firstaired', None):
            try:
                first_aired = datetime.datetime.strptime(show_info['firstaired'], '%Y-%m-%d')
                if first_aired:
                    if year_only:
                        return str(first_aired.year)
                    return str(first_aired.date())
            except (BaseException, Exception):
                pass
        if isinstance(show_obj, sickbeard.tv.TVShow):
            if year_only and show_obj.startyear:
                return '%s' % show_obj.startyear
            if not show_obj.sxe_ep_obj.get(1, {}).get(1, None):
                show_obj.get_all_episodes()
            first_ep_obj = show_obj.get_episode(1, 1, no_create=True)
            if isinstance(first_ep_obj, sickbeard.tv.TVEpisode) \
                    and isinstance(first_ep_obj.airdate, datetime.date) and 1900 < first_ep_obj.airdate.year:
                return '%s' % (first_ep_obj.airdate.year, first_ep_obj.airdate)[not year_only]

    def get_show_file_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self._show_metadata_filename)

    def get_episode_file_path(self, ep_obj):
        # type: (sickbeard.tv.TVEpisode) -> AnyStr
        return helpers.replace_extension(ep_obj.location, self._ep_nfo_extension)

    def get_fanart_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self.fanart_name)

    def get_poster_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self.poster_name)

    def get_banner_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self.banner_name)

    def get_episode_thumb_path(self, ep_obj):
        # type: (sickbeard.tv.TVEpisode) -> Optional[AnyStr]
        """
        Returns the path where the episode thumbnail should be stored.
        ep_obj: a TVEpisode instance for which to create the thumbnail
        """
        if ek.ek(os.path.isfile, ep_obj.location):

            tbn_filename = ep_obj.location.rpartition('.')

            if '' == tbn_filename[0]:
                tbn_filename = ep_obj.location
            else:
                tbn_filename = tbn_filename[0]

            return tbn_filename + '-thumb.jpg'

    def get_season_poster_path(self, show_obj, season):
        # type: (sickbeard.tv.TVShow, int) -> AnyStr
        """
        Returns the full path to the file for a given season poster.

        show_obj: a TVShow instance for which to generate the path
        season: a season number to be used for the path. Note that season 0
                means specials.
        """

        # Our specials thumbnail is, well, special
        if 0 == season:
            season_poster_filename = 'season-specials'
        else:
            season_poster_filename = 'season' + str(season).zfill(2)

        return ek.ek(os.path.join, show_obj.location, season_poster_filename + '-poster.jpg')

    def get_season_banner_path(self, show_obj, season):
        # type: (sickbeard.tv.TVShow, int) -> AnyStr
        """
        Returns the full path to the file for a given season banner.

        show_obj: a TVShow instance for which to generate the path
        season: a season number to be used for the path. Note that season 0
                means specials.
        """

        # Our specials thumbnail is, well, special
        if 0 == season:
            season_banner_filename = 'season-specials'
        else:
            season_banner_filename = 'season' + str(season).zfill(2)

        return ek.ek(os.path.join, show_obj.location, season_banner_filename + '-banner.jpg')

    def get_season_all_poster_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self.season_all_poster_name)

    def get_season_all_banner_path(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> AnyStr
        return ek.ek(os.path.join, show_obj.location, self.season_all_banner_name)

    def _show_data(self, show_obj, show_info=None):
        # type: (sickbeard.tv.TVShow, Any) -> Tuple[Optional[Union[bool, etree.Element]], Any]
        """
        This should be overridden by the implementing class. It should
        provide the content of the show metadata file.
        """
        return None, show_info

    @staticmethod
    def _valid_show(fetched_show_info, show_obj):
        # type: (Dict, sickbeard.tv.TVShow) -> bool
        """
        Test the integrity of fetched show data

        :param fetched_show_info: the object returned from the tvinfo source
        :param show_obj: Show that the fetched data relates to
        :return: True if fetched_show_obj is valid data otherwise False
        """
        if not (isinstance(fetched_show_info, dict) and
                isinstance(getattr(fetched_show_info, 'data', None), (list, dict)) and
                'seriesname' in getattr(fetched_show_info, 'data', [])):
            logger.log(u'Show %s not found on %s ' %
                       (show_obj.name, sickbeard.TVInfoAPI(show_obj.tvid).name), logger.WARNING)
            return False
        return True

    def _ep_data(self, ep_obj, show_info=None):
        # type: (sickbeard.tv.TVEpisode, Any) -> Tuple[Optional[Union[bool, etree.Element]], Any]
        """
        This should be overridden by the implementing class. It should
        provide the content of the episode metadata file.
        """
        return None, show_info

    def create_show_metadata(self, show_obj, force=False, show_info=None):
        # type: (sickbeard.tv.TVShow, bool, Any) -> Tuple[bool, Any]
        result = False
        if self.show_metadata and show_obj and (not self._has_show_metadata(show_obj) or force):
            logger.log('Metadata provider %s creating show metadata for %s' % (self.name, show_obj.name), logger.DEBUG)
            try:
                result = self.write_show_file(show_obj)
            except BaseTVinfoError as e:
                logger.log('Unable to find useful show metadata for %s on %s: %s' % (
                    self.name, sickbeard.TVInfoAPI(show_obj.tvid).name, ex(e)), logger.WARNING)

        if isinstance(result, tuple):
            result, show_info = result
        return result, show_info

    def create_episode_metadata(self, ep_obj, force=False, show_info=None):
        # type: (sickbeard.tv.TVEpisode, bool, Any) -> Tuple[bool, Any]
        result = False
        if self.episode_metadata and ep_obj and (not self.has_episode_metadata(ep_obj) or force):
            logger.log('Metadata provider %s creating episode metadata for %s' % (self.name, ep_obj.pretty_name()),
                       logger.DEBUG)
            try:
                result = self.write_ep_file(ep_obj)
            except BaseTVinfoError as e:
                logger.log('Unable to find useful episode metadata for %s on %s: %s' % (
                    self.name, sickbeard.TVInfoAPI(ep_obj.show_obj.tvid).name, ex(e)), logger.WARNING)

        if isinstance(result, tuple):
            result, show_info = result
        return result, show_info

    def update_show_indexer_metadata(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.show_metadata and show_obj and self._has_show_metadata(show_obj):
            logger.log(u'Metadata provider %s updating show indexer metadata file for %s' % (self.name, show_obj.name),
                       logger.DEBUG)

            nfo_file_path = self.get_show_file_path(show_obj)
            with ek.ek(io.open, nfo_file_path, 'r', encoding='utf8') as xmlFileObj:
                show_xml = etree.ElementTree(file=xmlFileObj)

            tvid = show_xml.find('indexer')
            prodid = show_xml.find('id')

            root = show_xml.getroot()
            show_tvid = str(show_obj.tvid)
            if None is not tvid:
                tvid.text = '%s' % show_tvid
            else:
                etree.SubElement(root, 'indexer').text = '%s' % show_tvid

            show_prodid = str(show_obj.prodid)
            if None is not prodid:
                prodid.text = '%s' % show_prodid
            else:
                etree.SubElement(root, 'id').text = '%s' % show_prodid

            # Make it purdy
            helpers.indent_xml(root)

            helpers.write_file(nfo_file_path, show_xml, xmltree=True, utf8=True)

            return True

    def create_fanart(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.fanart and show_obj and not self._has_fanart(show_obj):
            logger.log(u"Metadata provider " + self.name + " creating fanart for " + show_obj.name, logger.DEBUG)
            return self.save_fanart(show_obj)
        return False

    def create_poster(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.poster and show_obj and not self._has_poster(show_obj):
            logger.log(u"Metadata provider " + self.name + " creating poster for " + show_obj.name, logger.DEBUG)
            return self.save_poster(show_obj)
        return False

    def create_banner(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.banner and show_obj and not self._has_banner(show_obj):
            logger.log(u"Metadata provider " + self.name + " creating banner for " + show_obj.name, logger.DEBUG)
            return self.save_banner(show_obj)
        return False

    def create_episode_thumb(self, ep_obj, show_info=None):
        # type: (sickbeard.tv.TVEpisode, Any) -> Tuple[bool, Any]
        if self.episode_thumbnails and ep_obj and not self.has_episode_thumb(ep_obj):
            logger.log(u"Metadata provider " + self.name + " creating episode thumbnail for " + ep_obj.pretty_name(),
                       logger.DEBUG)
            return self.save_thumbnail(ep_obj, show_info)
        return False, None

    def create_season_posters(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.season_posters and show_obj:
            result = []
            for season, _ in iteritems(show_obj.sxe_ep_obj):
                if not self._has_season_poster(show_obj, season):
                    logger.log(u"Metadata provider " + self.name + " creating season posters for " + show_obj.name,
                               logger.DEBUG)
                    result = result + [self.save_season_posters(show_obj, season)]
            return all(result)
        return False

    def create_season_banners(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.season_banners and show_obj:
            result = []
            for season, _ in iteritems(show_obj.sxe_ep_obj):
                if not self._has_season_banner(show_obj, season):
                    logger.log(u"Metadata provider " + self.name + " creating season banners for " + show_obj.name,
                               logger.DEBUG)
                    result = result + [self.save_season_banners(show_obj, season)]
            return all(result)
        return False

    def create_season_all_poster(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.season_all_poster and show_obj and not self._has_season_all_poster(show_obj):
            logger.log(u"Metadata provider " + self.name + " creating season all poster for " + show_obj.name,
                       logger.DEBUG)
            return self.save_season_all_poster(show_obj)
        return False

    def create_season_all_banner(self, show_obj):
        # type: (sickbeard.tv.TVShow) -> bool
        if self.season_all_banner and show_obj and not self._has_season_all_banner(show_obj):
            logger.log(u"Metadata provider " + self.name + " creating season all banner for " + show_obj.name,
                       logger.DEBUG)
            return self.save_season_all_banner(show_obj)
        return False

    @staticmethod
    def _get_episode_thumb_url(ep_obj, show_info=None):
        # type: (sickbeard.tv.TVEpisode, Any) -> Optional[AnyStr, Any]
        """
        Returns the URL to use for downloading an episode's thumbnail. Uses
        theTVDB.com and TVRage.com data.

        :param ep_obj: a TVEpisode object for which to grab the thumb URL
        :return: URL to thumb
        """

        ep_obj_list = [ep_obj] + ep_obj.related_ep_obj

        # validate show
        if not helpers.validate_show(ep_obj.show_obj):
            return None

        ep_info = None

        # try all included episodes in case some have thumbs and others don't
        for cur_ep_obj in ep_obj_list:
            if TVINFO_TVDB == cur_ep_obj.show_obj.tvid:
                if not show_info:
                    show_lang = cur_ep_obj.show_obj.lang

                    try:
                        tvinfo_config = sickbeard.TVInfoAPI(TVINFO_TVDB).api_params.copy()
                        tvinfo_config['dvdorder'] = 0 != cur_ep_obj.show_obj.dvdorder
                        tvinfo_config['no_dummy'] = True

                        if show_lang and not 'en' == show_lang:
                            tvinfo_config['language'] = show_lang

                        t = sickbeard.TVInfoAPI(TVINFO_TVDB).setup(**tvinfo_config)

                        show_info = t[cur_ep_obj.show_obj.prodid]
                    except (BaseTVinfoEpisodenotfound, BaseTVinfoSeasonnotfound, TypeError):
                        pass

                if show_info:
                    try:
                        ep_info = show_info[cur_ep_obj.season][cur_ep_obj.episode]
                    except (BaseTVinfoEpisodenotfound, BaseTVinfoSeasonnotfound, TypeError):
                        pass
            else:
                ep_info = helpers.validate_show(cur_ep_obj.show_obj, cur_ep_obj.season, cur_ep_obj.episode)

            if not ep_info:
                continue

            thumb_url = getattr(ep_info, 'filename', None) \
                or (isinstance(ep_info, dict) and ep_info.get('filename', None))
            if thumb_url not in (None, False, ''):
                return thumb_url, show_info

        return None, show_info

    def write_show_file(self, show_obj, show_info=None):
        # type: (sickbeard.tv.TVShow, Any) -> Tuple[bool, Any]
        """
        Generates and writes show_obj's metadata under the given path to the
        filename given by get_show_file_path()

        show_obj: TVShow object for which to create the metadata

        path: An absolute or relative path where we should put the file. Note that
                the file name will be the default show_file_name.

        Note that this method expects that _show_data will return an ElementTree
        object. If your _show_data returns data in another format you'll need to
        override this method.
        """

        data = self._show_data(show_obj)
        if isinstance(data, tuple):
            data, show_info = data

        if not data:
            return False, show_info

        nfo_file_path = self.get_show_file_path(show_obj)

        logger.log(u'Writing show metadata file: %s' % nfo_file_path, logger.DEBUG)

        return helpers.write_file(nfo_file_path, data, xmltree=True, utf8=True), show_info

    def write_ep_file(self, ep_obj, show_info=None):
        # type: (sickbeard.tv.TVEpisode, Any) -> Tuple[bool, Any]
        """
        Generates and writes ep_obj's metadata under the given path with the
        given filename root. Uses the episode's name with the extension in
        _ep_nfo_extension.

        ep_obj: TVEpisode object for which to create the metadata

        file_name_path: The file name to use for this metadata. Note that the extension
                will be automatically added based on _ep_nfo_extension. This should
                include an absolute path.

        Note that this method expects that _ep_data will return an ElementTree
        object. If your _ep_data returns data in another format you'll need to
        override this method.
        """

        data = self._ep_data(ep_obj, show_info)
        if isinstance(data, tuple):
            data, show_info = data

        if not data:
            return False, show_info

        nfo_file_path = self.get_episode_file_path(ep_obj)

        logger.log(u'Writing episode metadata file: %s' % nfo_file_path, logger.DEBUG)

        return helpers.write_file(nfo_file_path, data, xmltree=True, utf8=True), show_info

    def save_thumbnail(self, ep_obj, show_info=None):
        # type: (sickbeard.tv.TVEpisode, Any) -> Tuple[bool, Any]
        """
        Retrieves a thumbnail and saves it to the correct spot. This method should not need to
        be overridden by implementing classes, changing get_episode_thumb_path and
        _get_episode_thumb_url should suffice.

        ep_obj: a TVEpisode object for which to generate a thumbnail
        """

        file_path = self.get_episode_thumb_path(ep_obj)

        if not file_path:
            logger.log(u"Unable to find a file path to use for this thumbnail, not generating it", logger.DEBUG)
            return False, None

        result = self._get_episode_thumb_url(ep_obj, show_info)
        if isinstance(result, tuple):
            thumb_url, show_info = result
        else:
            thumb_url = None
            show_info = None

        # if we can't find one then give up
        if not thumb_url:
            logger.log(u"No thumb is available for this episode, not creating a thumb", logger.DEBUG)
            return False, show_info

        thumb_data = metadata_helpers.getShowImage(thumb_url, show_name=ep_obj.show_obj.name)

        result = self._write_image(thumb_data, file_path)

        if not result:
            return False, show_info

        for cur_ep_obj in [ep_obj] + ep_obj.related_ep_obj:
            cur_ep_obj.hastbn = True

        return True, show_info

    def save_fanart(self, show_obj, which=None):
        # type: (sickbeard.tv.TVShow, Optional[AnyStr]) -> bool
        """
        Downloads a fanart image and saves it to the filename specified by fanart_name
        inside the show's root folder.

        show_obj: a TVShow object for which to download fanart
        """

        # use the default fanart name
        fanart_path = self.get_fanart_path(show_obj)

        fanart_data = self._retrieve_show_image('fanart', show_obj, which)

        if not fanart_data:
            logger.log(u"No fanart image was retrieved, unable to write fanart", logger.DEBUG)
            return False

        return self._write_image(fanart_data, fanart_path)

    def save_poster(self, show_obj, which=None):
        # type: (sickbeard.tv.TVShow, Optional[AnyStr]) -> bool
        """
        Downloads a poster image and saves it to the filename specified by poster_name
        inside the show's root folder.

        show_obj: a TVShow object for which to download a poster
        """

        # use the default poster name
        poster_path = self.get_poster_path(show_obj)

        poster_data = self._retrieve_show_image('poster', show_obj, which)

        if not poster_data:
            logger.log(u"No show poster image was retrieved, unable to write poster", logger.DEBUG)
            return False

        return self._write_image(poster_data, poster_path)

    def save_banner(self, show_obj, which=None):
        # type: (sickbeard.tv.TVShow, Optional[AnyStr]) -> bool
        """
        Downloads a banner image and saves it to the filename specified by banner_name
        inside the show's root folder.

        show_obj: a TVShow object for which to download a banner
        """

        # use the default banner name
        banner_path = self.get_banner_path(show_obj)

        banner_data = self._retrieve_show_image('banner', show_obj, which)

        if not banner_data:
            logger.log(u"No show banner image was retrieved, unable to write banner", logger.DEBUG)
            return False

        return self._write_image(banner_data, banner_path)

    def save_season_posters(self, show_obj, season):
        # type: (sickbeard.tv.TVShow, int) -> bool
        """
        Saves all season posters to disk for the given show.

        show_obj: a TVShow object for which to save the season thumbs

        Cycles through all seasons and saves the season posters if possible.
        """

        season_dict = self._season_image_dict(show_obj, season, 'seasons')
        result = []

        # Returns a nested dictionary of season art with the season
        # number as primary key. It's really overkill but gives the option
        # to present to user via ui to pick down the road.
        for cur_season in season_dict:

            cur_season_art = season_dict[cur_season]

            if 0 == len(cur_season_art):
                continue

            # Just grab whatever's there for now
            art_id, season_url = cur_season_art.popitem()

            season_poster_file_path = self.get_season_poster_path(show_obj, cur_season)

            if not season_poster_file_path:
                logger.log(u'Path for season ' + str(cur_season) + ' came back blank, skipping this season',
                           logger.DEBUG)
                continue

            season_data = metadata_helpers.getShowImage(season_url, show_name=show_obj.name)

            if not season_data:
                logger.log(u'No season poster data available, skipping this season', logger.DEBUG)
                continue

            result = result + [self._write_image(season_data, season_poster_file_path)]

        if result:
            return all(result)
        return False

    def save_season_banners(self, show_obj, season):
        # type: (sickbeard.tv.TVShow, int) -> bool
        """
        Saves all season banners to disk for the given show.

        show_obj: a TVShow object for which to save the season thumbs

        Cycles through all seasons and saves the season banners if possible.
        """

        season_dict = self._season_image_dict(show_obj, season, 'seasonwides')
        result = []

        # Returns a nested dictionary of season art with the season
        # number as primary key. It's really overkill but gives the option
        # to present to user via ui to pick down the road.
        for cur_season in season_dict:

            cur_season_art = season_dict[cur_season]

            if 0 == len(cur_season_art):
                continue

            # Just grab whatever's there for now
            art_id, season_url = cur_season_art.popitem()

            season_banner_file_path = self.get_season_banner_path(show_obj, cur_season)

            if not season_banner_file_path:
                logger.log(u'Path for season ' + str(cur_season) + ' came back blank, skipping this season',
                           logger.DEBUG)
                continue

            season_data = metadata_helpers.getShowImage(season_url, show_name=show_obj.name)

            if not season_data:
                logger.log(u'No season banner data available, skipping this season', logger.DEBUG)
                continue

            result = result + [self._write_image(season_data, season_banner_file_path)]

        if result:
            return all(result)
        return False

    def save_season_all_poster(self, show_obj, which=None):
        # type: (sickbeard.tv.TVShow, Optional[AnyStr]) -> bool
        # use the default season all poster name
        poster_path = self.get_season_all_poster_path(show_obj)

        poster_data = self._retrieve_show_image('poster', show_obj, which)

        if not poster_data:
            logger.log(u"No show poster image was retrieved, unable to write season all poster", logger.DEBUG)
            return False

        return self._write_image(poster_data, poster_path)

    def save_season_all_banner(self, show_obj, which=None):
        # type: (sickbeard.tv.TVShow, Optional[AnyStr]) -> bool
        # use the default season all banner name
        banner_path = self.get_season_all_banner_path(show_obj)

        banner_data = self._retrieve_show_image('banner', show_obj, which)

        if not banner_data:
            logger.log(u"No show banner image was retrieved, unable to write season all banner", logger.DEBUG)
            return False

        return self._write_image(banner_data, banner_path)

    @staticmethod
    def _write_image(image_data, image_path, force=False):
        # type: (bytes, AnyStr, bool) -> bool
        """
        Saves the data in image_data to the location image_path. Returns True/False
        to represent success or failure.

        image_data: binary image data to write to file
        image_path: file location to save the image to
        """

        # don't bother overwriting it
        if not force and ek.ek(os.path.isfile, image_path):
            logger.log(u"Image already exists, not downloading", logger.DEBUG)
            return False

        if not image_data:
            logger.log(u"Unable to retrieve image, skipping", logger.WARNING)
            return False

        image_dir = ek.ek(os.path.dirname, image_path)

        try:
            if not ek.ek(os.path.isdir, image_dir):
                logger.log(u"Metadata dir didn't exist, creating it at " + image_dir, logger.DEBUG)
                ek.ek(os.makedirs, image_dir)
                helpers.chmod_as_parent(image_dir)

            outFile = ek.ek(open, image_path, 'wb')
            outFile.write(image_data)
            outFile.close()
            helpers.chmod_as_parent(image_path)
        except IOError as e:
            logger.log(
                u"Unable to write image to " + image_path + " - are you sure the show folder is writable? " + ex(e),
                logger.ERROR)
            return False

        return True

    def _retrieve_show_image(self, image_type, show_obj, which=None):
        # type: (AnyStr, sickbeard.tv.TVShow, bool) -> Optional[bytes, List[AnyStr]]
        """
        Gets an image URL from theTVDB.com, fanart.tv and TMDB.com, downloads it and returns the data.
        If type is fanart, multiple image src urls are returned instead of a single data image.

        image_type: type of image to retrieve (currently supported: fanart, poster, banner, poster_thumb, banner_thumb)
        show_obj: a TVShow object to use when searching for the image
        which: optional, a specific numbered poster to look for

        Returns: the binary image data if available, or else None
        """
        show_lang = show_obj.lang

        try:
            # There's gotta be a better way of doing this but we don't wanna
            # change the language value elsewhere
            tvinfo_config = sickbeard.TVInfoAPI(show_obj.tvid).api_params.copy()
            if image_type.startswith('fanart'):
                tvinfo_config['fanart'] = True
            elif image_type.startswith('poster'):
                tvinfo_config['posters'] = True
            else:
                tvinfo_config['banners'] = True
            tvinfo_config['dvdorder'] = 0 != show_obj.dvdorder

            if show_lang and not 'en' == show_lang:
                tvinfo_config['language'] = show_lang

            t = sickbeard.TVInfoAPI(show_obj.tvid).setup(**tvinfo_config)
            show_info = t[show_obj.prodid, False]
        except (BaseTVinfoError, IOError) as e:
            logger.log(u"Unable to look up show on " + sickbeard.TVInfoAPI(
                show_obj.tvid).name + ", not downloading images: " + ex(e), logger.WARNING)
            return None

        if not self._valid_show(show_info, show_obj):
            return None

        return_links = False
        if 'fanart_all' == image_type:
            return_links = True
            image_type = 'fanart'

        if image_type not in ('poster', 'banner', 'fanart', 'poster_thumb', 'banner_thumb'):
            logger.log(u"Invalid image type " + str(image_type) + ", couldn't find it in the " + sickbeard.TVInfoAPI(
                show_obj.tvid).name + " object", logger.ERROR)
            return None

        image_urls = []
        init_url = None
        alt_tvdb_urls = []

        def build_url(s_o, image_mode):
            _urls = [[], []]
            _url = s_o[image_mode]
            if _url and _url.startswith('http'):
                if 'poster' == image_mode:
                    _url = re.sub('posters', '_cache/posters', _url)
                elif 'banner' == image_mode:
                    _url = re.sub('graphical', '_cache/graphical', _url)
                _urls[0].append(_url)

                try:
                    alt_url = '%swww.%s%s' % re.findall(
                        r'(https?://)(?:artworks\.)?(thetvdb\.[^/]+/banners/[^\d]+[^.]+)(?:_t)(.*)', _url)[0][0:3]
                    if alt_url not in _urls[0]:
                        _urls[1].append(alt_url)
                except (IndexError, Exception):
                    try:
                        alt_url = '%sartworks.%s_t%s' % re.findall(
                            r'(https?://)(?:www\.)?(thetvdb\.[^/]+/banners/[^\d]+[^.]+)(.*)', _url)[0][0:3]
                        if alt_url not in _urls[0]:
                            _urls[1].append(alt_url)
                    except (IndexError, Exception):
                        pass
            return _urls

        if 'poster_thumb' == image_type:
            if None is not getattr(show_info, image_type, None):
                image_urls, alt_tvdb_urls = build_url(show_info, image_type)
            elif None is not getattr(show_info, 'poster', None):
                image_urls, alt_tvdb_urls = build_url(show_info, 'poster')

            for item in self._fanart_urls_from_show(show_obj, image_type, show_lang, True) or []:
                image_urls.append(item[2])
            if 0 == len(image_urls):
                for item in self._tmdb_image_url(show_obj, image_type) or []:
                    image_urls.append(item[2])

        elif 'banner_thumb' == image_type:
            if None is not getattr(show_info, image_type, None):
                image_urls, alt_tvdb_urls = build_url(show_info, image_type)
            elif None is not getattr(show_info, 'banner', None):
                image_urls, alt_tvdb_urls = build_url(show_info, 'banner')
            for item in self._fanart_urls_from_show(show_obj, image_type, show_lang, True) or []:
                image_urls.append(item[2])
        else:
            for item in self._fanart_urls_from_show(show_obj, image_type, show_lang) or []:
                image_urls.append(item[2])

            if None is not getattr(show_info, image_type, None):
                image_url = show_info[image_type]
                if image_url:
                    image_urls.append(image_url)
                    if 'poster' == image_type:
                        init_url = image_url

            # check extra provided images in '_banners' key
            if None is not getattr(show_info, '_banners', None) and \
                    isinstance(show_info['_banners'].get(image_type, None), (list, dict)):
                for res, value in iteritems(show_info['_banners'][image_type]):
                    for item in itervalues(value):
                        image_urls.append(item['bannerpath'])

            if 0 == len(image_urls) or 'fanart' == image_type:
                for item in self._tmdb_image_url(show_obj, image_type) or []:
                    image_urls.append('%s?%s' % (item[2], item[0]))

        img_data = len(image_urls) or None
        if img_data:
            # remove duplicates, keeping order
            image_urls = list(OrderedDict.fromkeys(image_urls))
            if return_links:
                return image_urls
            else:
                img_data = metadata_helpers.getShowImage(
                    (init_url, image_urls[0])[None is init_url], which, show_obj.name, bool(len(alt_tvdb_urls)))
                if None is img_data and len(alt_tvdb_urls):
                    for url in alt_tvdb_urls:
                        image_data = metadata_helpers.getShowImage(
                            (init_url, url)[None is init_url], which, show_obj.name)
                        if None is not image_data:
                            break

        if None is not img_data:
            return img_data

        if None is not img_data:
            return img_data

    def _season_image_dict(self, show_obj, season, image_type):
        # type: (sickbeard.tv.TVShow, int, AnyStr) -> Dict[int, Dict[int, AnyStr]]
        """
        image_type : Type of image to fetch, 'seasons' or 'seasonwides'
        image_type type : String

        Should return a dict like:

        result = {<season number>:
                    {1: '<url 1>', 2: <url 2>, ...},}
        """
        result = {}

        try:
            # There's gotta be a better way of doing this but we don't wanna
            # change the language value elsewhere
            tvinfo_config = sickbeard.TVInfoAPI(show_obj.tvid).api_params.copy()
            tvinfo_config[image_type] = True
            tvinfo_config['dvdorder'] = 0 != show_obj.dvdorder

            if 'en' != getattr(show_obj, 'lang', None):
                tvinfo_config['language'] = show_obj.lang

            t = sickbeard.TVInfoAPI(show_obj.tvid).setup(**tvinfo_config)
            tvinfo_obj_show = t[show_obj.prodid]
        except (BaseTVinfoError, IOError) as e:
            logger.log(u'Unable to look up show on ' + sickbeard.TVInfoAPI(
                show_obj.tvid).name + ', not downloading images: ' + ex(e), logger.WARNING)
            return result

        if not self._valid_show(tvinfo_obj_show, show_obj):
            return result

        season_images = getattr(tvinfo_obj_show, 'banners', {}).get(
            ('season', 'seasonwide')['seasonwides' == image_type], {}).get(season, {})
        for image_id in season_images:
            if season not in result:
                result[season] = {}
            result[season][image_id] = season_images[image_id]['bannerpath']

        return result

    def retrieveShowMetadata(self, folder):
        # type: (AnyStr) -> Union[Tuple[int, int, AnyStr], Tuple[None, None, None]]
        """
        Used only when mass adding Existing Shows,
         using previously generated Show metadata to reduce the need to query TVDB.
        """

        from sickbeard.indexers.indexer_config import TVINFO_TVDB

        empty_return = (None, None, None)

        metadata_path = ek.ek(os.path.join, folder, self._show_metadata_filename)

        if not ek.ek(os.path.isdir, folder) or not ek.ek(os.path.isfile, metadata_path):
            logger.log(u"Can't load the metadata file from " + repr(metadata_path) + ", it doesn't exist", logger.DEBUG)
            return empty_return

        logger.log(u"Loading show info from metadata file in " + folder, logger.DEBUG)

        try:
            with ek.ek(io.open, metadata_path, 'r', encoding='utf8') as xmlFileObj:
                showXML = etree.ElementTree(file=xmlFileObj)

            if None is showXML.findtext('title') \
                    or (None is showXML.find('//uniqueid[@type="tvdb"]')
                        and (None is showXML.findtext('tvdbid')
                             and None is showXML.findtext('id'))
                        and None is showXML.findtext('indexer')):
                logger.log(u"Invalid info in tvshow.nfo (missing name or id):"
                           + str(showXML.findtext('title')) + ' '
                           + str(showXML.findtext('indexer')) + ' '
                           + str(showXML.findtext('tvdbid')) + ' '
                           + str(showXML.findtext('id')))
                return empty_return

            name = showXML.findtext('title')

            try:
                tvid = int(showXML.findtext('indexer'))
            except (BaseException, Exception):
                tvid = None

            prodid = showXML.find('//uniqueid[@type="tvdb"]')
            if None is not prodid:
                prodid = int(prodid.text)
                tvid = TVINFO_TVDB
            elif None is not showXML.findtext('tvdbid'):
                prodid = int(showXML.findtext('tvdbid'))
                tvid = TVINFO_TVDB
            elif None is not showXML.findtext('id'):
                prodid = int(showXML.findtext('id'))
                try:
                    tvid = TVINFO_TVDB if [s for s in showXML.findall('.//*')
                                           if s.text and -1 != s.text.find('thetvdb.com')] else tvid
                except (BaseException, Exception):
                    pass
            else:
                logger.log(u"Empty <id> or <tvdbid> field in NFO, unable to find a ID", logger.WARNING)
                return empty_return

            if None is prodid:
                logger.log(u"Invalid Show ID (%s), not using metadata file" % prodid, logger.WARNING)
                return empty_return

        except (BaseException, Exception) as e:
            logger.log(
                u"There was an error parsing your existing metadata file: '" + metadata_path + "' error: " + ex(e),
                logger.WARNING)
            return empty_return

        return tvid, prodid, name

    @staticmethod
    def _tmdb_image_url(show_obj, image_type):
        # type: (sickbeard.tv.TVShow, AnyStr) -> Optional[List[List[int, int, AnyStr]]]
        types = {'poster': 'poster_path',
                 'banner': None,
                 'fanart': 'backdrop_path',
                 'fanart_all': 'backdrops',
                 'poster_thumb': 'poster_path',
                 'banner_thumb': None}

        # get TMDB configuration info
        TMDB.API_KEY = sickbeard.TMDB_API_KEY
        config = TMDB.Configuration()
        response = config.info()
        base_url = response['images']['base_url']
        sizes = response['images']['poster_sizes']

        def size_str_to_int(x):
            return float('inf') if 'original' == x else int(x[1:])

        max_size = max(sizes, key=size_str_to_int)

        try:
            itemlist = []
            for (src, name) in [(indexer_config.TVINFO_TVDB, 'tvdb'), (indexer_config.TVINFO_IMDB, 'imdb'),
                                (indexer_config.TVINFO_TVRAGE, 'tvrage')]:
                is_id = show_obj.ids.get(src, {}).get('id', None)
                if not is_id:
                    continue

                result = TMDB.Find(is_id).info(**{'external_source': '%s_id' % name})
                if 'tv_results' not in result or not len(result['tv_results']):
                    continue

                tmdb_show = result['tv_results'][0]

                if 'fanart' == image_type:
                    tv_obj = TMDB.TV(tmdb_show['id'])
                    rjson_info = tv_obj.info(**{'append_to_response': 'images', 'include_image_language': 'en,null'})
                    rjson_img = rjson_info['images']
                    for art in rjson_img[types['fanart_all']] or []:
                        if 'vote_average' not in art or 'file_path' not in art:
                            continue
                        art_likes = art['vote_average']
                        url = u'%s%s%s' % (base_url, max_size, art['file_path'])
                        itemlist += [[tmdb_show['id'], art_likes, url]]

                    itemlist.sort(key=lambda a: (a[1]), reverse=True)
                    return itemlist

                elif tmdb_show[types[image_type]]:
                    return [[tmdb_show['id'],
                             tmdb_show['vote_average'],
                             '%s%s%s' % (base_url, max_size, tmdb_show[types[image_type]])]]

        except (BaseException, Exception):
            pass

        logger.log(u'Could not find any %s images on TMDB for %s' % (image_type, show_obj.name), logger.DEBUG)

    def _fanart_urls_from_show(self, show_obj, image_type='banner', lang='en', thumb=False):
        # type: (sickbeard.tv.TVShow, AnyStr, AnyStr, bool) -> Optional[List[int, int, AnyStr]]
        try:
            tvdb_id = show_obj.ids.get(indexer_config.TVINFO_TVDB, {}).get('id', None)
            if tvdb_id:
                return self._fanart_urls(tvdb_id, image_type, lang, thumb)
        except (BaseException, Exception):
            pass

        logger.log(u'Could not find any %s images on Fanart.tv for %s' % (image_type, show_obj.name), logger.DEBUG)

    @staticmethod
    def _fanart_urls(tvdb_id, image_type='banner', lang='en', thumb=False):
        # type: (int, AnyStr, AnyStr, bool) -> Optional[List[int, int, AnyStr]]
        types = {'poster': fanart.TYPE.TV.POSTER,
                 'banner': fanart.TYPE.TV.BANNER,
                 'fanart': fanart.TYPE.TV.BACKGROUND,
                 'poster_thumb': fanart.TYPE.TV.POSTER,
                 'banner_thumb': fanart.TYPE.TV.BANNER}

        try:
            if tvdb_id:
                request = fanartRequest(apikey=sickbeard.FANART_API_KEY, tvdb_id=tvdb_id, types=types[image_type])
                resp = request.response()
                itemlist = []
                dedupe = []
                for art in filter_iter(lambda i: 10 < len(i.get('url', '')) and (lang == i.get('lang', '')[0:2]),
                                       # remove "[0:2]" ... to strictly use only data where "en" is at source
                                       resp[types[image_type]]):  # type: dict
                    try:
                        url = (art['url'], art['url'].replace('/fanart/', '/preview/'))[thumb]
                        if url not in dedupe:
                            dedupe += [url]
                            itemlist += [
                                [int(art['id']), int(art['likes']), url]
                            ]
                    except (BaseException, Exception):
                        continue

                itemlist.sort(key=lambda a: (a[1], a[0]), reverse=True)
                return itemlist

        except (BaseException, Exception):
            raise

    def retrieve_show_image(self, image_type, show_obj, which=None):
        # type: (AnyStr, sickbeard.tv.TVShow, bool) -> Optional[bytes]
        return self._retrieve_show_image(image_type=image_type, show_obj=show_obj, which=which)

    def write_image(self, image_data, image_path, force=False):
        # type: (bytes, AnyStr, bool) -> bool
        return self._write_image(image_data=image_data, image_path=image_path, force=force)
