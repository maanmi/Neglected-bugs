
if __name__ == '__main__':
    import sys
    sys.path.append('.')
    from reffinder.web import app
    app.run(debug=True)
