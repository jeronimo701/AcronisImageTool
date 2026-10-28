from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from io import BytesIO

from app.source_service import SourceConfig, SourceFile, TransferCancelled, copy_source_file
from app.web_source import WEB_ENDPOINT, WEB_FOLDER, resolve_location, list_web_files


class WebSourceTests(TestCase):
    def setUp(self):
        self.config = SourceConfig('web', WEB_ENDPOINT, WEB_FOLDER, '', '', True)

    def test_folder_links(self):
        self.assertEqual(resolve_location(WEB_ENDPOINT, WEB_ENDPOINT + '/#/'), (WEB_ENDPOINT, ''))
        self.assertEqual(resolve_location(WEB_ENDPOINT, WEB_ENDPOINT + '/#/a%20b/'), (WEB_ENDPOINT, 'a b/'))
        self.assertEqual(resolve_location(WEB_ENDPOINT, 'a b/'), (WEB_ENDPOINT, 'a b/'))

    def test_pagination_and_recursive_keys(self):
        def page(key, next_token=''):
            return BytesIO(('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                f'<Contents><Key>{WEB_FOLDER}{key}</Key><Size>5000000000</Size>'
                '<LastModified>2025-08-14T05:58:59Z</LastModified></Contents>'
                f'<IsTruncated>{str(bool(next_token)).lower()}</IsTruncated>'
                f'<NextContinuationToken>{next_token}</NextContinuationToken></ListBucketResult>').encode())
        with patch('app.web_source.urlopen', side_effect=[page('sub/a.tib', 'next'), page('b.tibx')]) as request:
            files = list_web_files(self.config)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].size, 5000000000)
        self.assertIn('continuation-token=next', request.call_args_list[1].args[0].full_url)
        self.assertEqual({str(f.relative_path) for f in files}, {'sub/a.tib', 'b.tibx'})

    def test_download_size_mismatch_and_cancel_keep_existing(self):
        from pathlib import PurePosixPath
        item = SourceFile('web', WEB_ENDPOINT, '', PurePosixPath('a.tib'), WEB_ENDPOINT+'/a.tib', 'a.tib', 4, datetime.now())
        with TemporaryDirectory() as folder:
            target = Path(folder)/'a.tib'
            target.write_bytes(b'old')
            for payload, cancelled, error in [(b'bad', False, OSError), (b'data', True, TransferCancelled)]:
                with patch('app.web_source.urlopen', return_value=BytesIO(payload)):
                    with self.assertRaises(error):
                        copy_source_file(item, self.config, target, lambda *args: None, lambda: cancelled)
                self.assertEqual(target.read_bytes(), b'old')
                self.assertFalse(target.with_suffix('.tib.part').exists())
            with patch('app.web_source.urlopen', return_value=BytesIO(b'data')):
                copy_source_file(item, self.config, target, lambda *args: None, lambda: False)
            self.assertEqual(target.read_bytes(), b'data')


if __name__ == '__main__':
    main()
