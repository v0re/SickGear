# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import urllib
import datetime

import generic
from sickbeard import classes, show_name_helpers, logger, tvcache


class animenzb(generic.NZBProvider):

    def __init__(self):
        generic.NZBProvider.__init__(self, 'animenzb', True, True)
        self.cache = animenzbCache(self)
        self.url = 'http://animenzb.com/'

    def _get_season_search_strings(self, ep_obj):
        return [x for x in show_name_helpers.makeSceneSeasonSearchString(self.show, ep_obj)]

    def _get_episode_search_strings(self, ep_obj, add_string=''):
        return [x for x in show_name_helpers.makeSceneSearchString(self.show, ep_obj)]

    def _doSearch(self, search_string, search_mode='eponly', epcount=0, age=0):
        if self.show and not self.show.is_anime:
            logger.log(u'%s is not an anime skipping ...' % self.show.name)
            return []

        params = {
            'cat': 'anime',
            'q': search_string.encode('utf-8'),
            'max': '100'
        }

        search_url = self.url + 'rss?' + urllib.urlencode(params)

        logger.log(u'Search url: %s' % search_url, logger.DEBUG)

        data = self.cache.getRSSFeed(search_url)
        if not data:
            return []

        if 'entries' in data:

            items = data.entries
            results = []

            for curItem in items:
                (title, url) = self._get_title_and_url(curItem)

                if title and url:
                    results.append(curItem)
                else:
                    logger.log(
                        u'The data returned from %s is incomplete, this result is unusable' % self.name,
                        logger.DEBUG)

            return results

        return []

    def findPropers(self, date=None):

        results = []

        for item in self._doSearch('v2|v3|v4|v5'):

            (title, url) = self._get_title_and_url(item)

            if item.has_key('published_parsed') and item['published_parsed']:
                result_date = item.published_parsed
                if result_date:
                    result_date = datetime.datetime(*result_date[0:6])
            else:
                logger.log(u'Unable to figure out the date for entry %s, skipping it' % title)
                continue

            if not date or result_date > date:
                search_result = classes.Proper(title, url, result_date, self.show)
                results.append(search_result)

        return results


class animenzbCache(tvcache.TVCache):

    def __init__(self, provider):

        tvcache.TVCache.__init__(self, provider)


        self.minTime = 20

    def _getRSSData(self):

        params = {
            'cat': 'anime'.encode('utf-8'),
            'max': '100'.encode('utf-8')
        }

        rss_url = self.provider.url + 'rss?' + urllib.urlencode(params)

        logger.log(u'%s cache update URL: %s' % (self.provider.name, rss_url), logger.DEBUG)

        data = self.getRSSFeed(rss_url)

        if data and 'entries' in data:
            return data.entries
        else:
            return []


provider = animenzb()