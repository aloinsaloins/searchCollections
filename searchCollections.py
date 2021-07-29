import urllib.request
import urllib.parse
from xml.etree.ElementTree import ElementTree
import json
import time
import webbrowser
import PySimpleGUI as sg

adrs = ""
title = ""
rakutenKEY = ""
calilKEY = ""


def getGeocode(adrs) -> str:
    # 住所から緯度経度の取得（Geocoding API）
    geo = "https://www.geocoding.jp/api/?q={}".format(urllib.parse.quote(adrs))
    try:
        with urllib.request.urlopen(geo) as res:
            et = ElementTree()
            et.parse(res)
            lat = et.find("./coordinate/lat").text
            lng = et.find("./coordinate/lng").text
    except urllib.error.HTTPError as err:
        sg.popup(err.code)
    except urllib.error.URLError as err:
        sg.popup(err.reason)

    geocode = str(lng) + "," + str(lat)
    return geocode


def getLibrary(geoCode) -> str:
    # 緯度経度から図書館情報取得（Calil API）
    getLibraryURL = "https://api.calil.jp/library?appkey={}".format(
        urllib.parse.quote(calilKEY))
    getLibraryurl = '{}&geocode={}'.format(
        getLibraryURL, geoCode)

    try:
        with urllib.request.urlopen(getLibraryurl) as res:
            et = ElementTree()
            et.parse(res)
            formalName = et.find("./Library/formal").text
            systemid = et.find("./Library/systemid").text
    except urllib.error.HTTPError as err:
        sg.popup(err.code)
    except urllib.error.URLError as err:
        sg.popup(err.reason)
    return (formalName, systemid)


def getIsbn(title) -> str:
    # 書籍名からISBNを取得（Rakuten API）
    searchBooks = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404?applicationId={}&title={}".format(
        urllib.parse.quote(rakutenKEY), urllib.parse.quote(title))
    try:
        with urllib.request.urlopen(searchBooks) as res:
            booksRet = json.load(res)
    except urllib.error.HTTPError as err:
        sg.popup(err.code)
    except urllib.error.URLError as err:
        sg.popup(err.reason)

    isbn = booksRet["Items"][0]["Item"]["isbn"]
    gotTitle = booksRet["Items"][0]["Item"]["title"]
    return (isbn, gotTitle)


def isCollection(isbn, systemid):
    # isbnから蔵書の有無と貸し出し情報取得（Calil API）
    searchCollection = "https://api.calil.jp/check?appkey={}&isbn={}&systemid={}&format=json&callback=no".format(
        urllib.parse.quote(calilKEY), urllib.parse.quote(isbn), urllib.parse.quote(systemid))
    try:
        with urllib.request.urlopen(searchCollection) as res:
            collectionRet = json.load(res)
            while True:
                if collectionRet["continue"] == 0:
                    break
                # Calilの指定でポーリングは2秒以上開ける
                time.sleep(2)
                checkCollection = "https://api.calil.jp/check?session={}&format=json&callback=no".format(
                    urllib.parse.quote(collectionRet["session"]))
                try:
                    with urllib.request.urlopen(checkCollection) as res:
                        collectionRet = json.load(res)
                except urllib.error.HTTPError as err:
                    sg.popup(err.code)
                except urllib.error.URLError as err:
                    sg.popup(err.reason)

    except urllib.error.HTTPError as err:
        sg.popup(err.code)

    except urllib.error.URLError as err:
        sg.popup(err.reason)

    libkey = collectionRet["books"][isbn][systemid]["libkey"]

    libraries = {}
    for x in libkey:
        libraries[x] = libkey[x]

    return libraries


def main():
    #  セクション1 - オプションの設定と標準レイアウト
    sg.theme("Dark Blue 3")

    layout = [
        [sg.Text("書名と自治体名を入力してください")],
        [sg.Text("書名", size=(15, 1)), sg.InputText("")],
        [sg.Text("自治体名", size=(15, 1)), sg.InputText("")],
        [sg.Submit(button_text="実行")],
        [sg.Submit(button_text="終了")],
    ]

    # セクション 2 - ウィンドウの生成
    window = sg.Window("図書館蔵書検索 Supported by Rakuten Developers", layout)

    # セクション 3 - イベントループ
    while True:
        event, values = window.read()

        if event == ("終了" or sg.WINDOW_CLOSED) or event is None:
            break

        if event == "実行":
            title = values[0]
            adrs = values[1]
            if (title or adrs) is None:
                show_message = "書名と自治体名は両方入力してください"
                sg.popup(show_message)
                continue
            (isbn, gotTitle) = getIsbn(title)
            if isbn is None:
                show_message = "[" + title + "]" + "を含む書籍は見つかりませんでした。"
                sg.popup(show_message)
                continue
            geoCode = getGeocode(adrs)
            if geoCode is None:
                show_message = "入力した市区町村が見つかりませんでした。"
                sg.popup(show_message)
                continue
            (formalName, systemid) = getLibrary(geoCode)
            if (formalName or systemid) is None:
                show_message = "入力した市区町村に図書館は見つかりませんでした。"
                sg.popup(show_message)
                continue
            libraries = isCollection(isbn, systemid)
            if len(libraries) == 0:
                show_message = "蔵書はありませんでした。"
                sg.popup(show_message)
                continue

            urls = {}
            for x in libraries:
                urls[x + ":" + libraries[x]] = "https://calil.jp/library/search?s=" + \
                    systemid + "&k=" + x

            items = sorted(urls.keys())

            sg.theme("DarkBlue")
            layout2 = [
                [sg.Text("蔵書:" + gotTitle, tooltip="https://calil.jp/book/" +
                         isbn, enable_events=True, key=f'URL {"https://calil.jp/book/" + isbn}')],
                [sg.Text("--所蔵図書館--")],
                [[sg.Text(txt, tooltip=urls[txt], enable_events=True,
                          key=f'URL {urls[txt]}')] for txt in items],
                [sg.Submit(button_text="終了")]
            ]

            window2 = sg.Window("検索結果", layout2)

            while True:
                event, values = window2.read()
                if event == ("終了" or sg.WINDOW_CLOSED) or event is None:
                    break
                elif event.startswith("URL "):
                    url = event.split(' ')[1]
                    webbrowser.open(url)
            window2.close()

    window.close()


if __name__ == "__main__":
    main()
